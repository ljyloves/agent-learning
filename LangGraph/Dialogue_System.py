import os
import asyncio
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from tavily import TavilyClient
from searchState import SearchState


load_dotenv()

llm = ChatOpenAI(
    model=os.getenv("LLM_MODEL_ID", "qwen3.6-plus"),
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    temperature=0.7,
)

travily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


#Nodes
def understand_query_node(state: SearchState) -> SearchState:
    # 步骤1：理解用户查询并生成搜索关键词
    user_message = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            user_message = msg.content
            break
    
    understand_prompt = f"""
请完成两个任务：
1. 简洁总结用户想要了解什么
2. 生成最适合搜索的关键词（中英文均可，要精准）

---
【参考示例】
用户输入：想自己部署一个本地的AI画图工具，电脑是Mac M2芯片的，内存16G，有什么推荐的方案吗？最好不用敲太多代码。
理解：用户希望在配置为Mac M2芯片、16G内存的电脑上，寻找低代码/免代码门槛的本地AI绘画部署方案。
搜索词：Mac M2 16G local AI image generator GUI OR Mac M2 部署 本地 AI 绘画 一键安装 (Stable Diffusion OR Midjourney alternatives)
---

【任务开始】
用户输入："{user_message}"

请严格按照以下格式输出结果：
理解：[用户需求总结]
搜索词：[最佳搜索关键词]"""
    
    response = llm.invoke([SystemMessage(content = understand_prompt)])
    response_text = response.content
    search_query = user_message

    if "搜索词：" in response_text:
        search_query = response_text.split("搜索词：")[1].strip()
    elif "搜索关键词：" in response_text:
        search_query = response_text.split("搜索关键词：")[1].strip()

    return {
        "user_query": response_text,
        "search_query": search_query,
        "step": "understood",
        "messages": [AIMessage(content = f"我理解你的需求：{response_text}，接下来我会帮你搜索相关信息。")]
    }

def tavily_search_node(state: SearchState) -> SearchState:
    # 步骤2：使用Tavily API进行搜索
    search_query = state["search_query"]
    try:
        print(f"🔍 正在使用Tavily搜索: {search_query}")
        tavily_response = travily_client.search(
            query = search_query, 
            search_depth = "basic",
            include_answer = True,
            include_raw_content = False,
            num_results=5
        )
        search_results = []

        if tavily_response.get("answer"):
            search_results = f"综合答案：\n{tavily_response['answer']}\n\n"

        if tavily_response.get("results"):
            search_results += "相关信息:\n"
            for i, result in enumerate(tavily_response["results"][:3], 1):
                title = result.get("title", "无标题")
                url = result.get("url", "无链接")
                content = result.get("content", "无内容")
                search_results += f"{i}. {title}\n{content}\n来源:{url}\n\n"

        if not search_results:
            search_results = "抱歉，未找到相关信息。"
    
        return {
            "search_results": search_results,
            "step": "searched",
            "messages": [AIMessage(content = f"正在为您整理答案...")]
        }
    except Exception as e:
        print(f"❌ 搜索过程中发生错误: {str(e)}")
        return {
            "search_results": "抱歉，搜索过程中发生错误。",
            "step": "search_failed",
            "messages": [AIMessage(content = f"抱歉，搜索过程中发生错误。")]
        }
    
def generate_answer_node(state: SearchState) -> SearchState:
    # 步骤3：根据搜索结果生成最终答案
    if state["step"] == "search_failed":
        fallback_prompt = f"""
搜索API暂时不可用，请基于您的知识回答用户的问题：

用户问题：{state['user_query']}

请提供一个有用的回答，并说明这是基于已有知识的回答。
"""
        response = llm.invoke([SystemMessage(content = fallback_prompt)])
        return {
            "final_answer": response.content,
            "step": "completed",
            "messages": [AIMessage(content = response.content)]
        }
    
    answer_prompt = f"""请根据以下搜索结果，结合你的知识，回答用户的问题：
用户问题：{state['user_query']}

搜索结果：{state['search_results']}
请要求：
1. 综合搜索结果，提供准确、有用的回答
2. 如果是技术问题，提供具体的解决方案或代码
3. 引用重要信息的来源
4. 回答要结构清晰、易于理解
5. 如果搜索结果不够完整，请说明并提供补充建议"""
    response = llm.invoke([SystemMessage(content = answer_prompt)])
    return {
        "final_answer": response.content,
        "step": "completed",
        "messages": [AIMessage(content = response.content)]
    }

#构建workflow:
def create_search_assistant():
    workflow = StateGraph(SearchState)

    #添加三个节点
    workflow.add_node("understand", understand_query_node)
    workflow.add_node("search", tavily_search_node)
    workflow.add_node("answer", generate_answer_node)

    #添加边,设置线性流程
    workflow.add_edge(START, "understand")
    workflow.add_edge("understand", "search")
    workflow.add_edge("search", "answer")
    workflow.add_edge("answer", END)

    #编译图
    memory = InMemorySaver()
    app = workflow.compile(checkpointer=memory)

    return app

async def main():

    if not os.getenv("TAVILY_API_KEY"):
        print("⚠️ 警告：未找到TAVILY_API_KEY环境变量，搜索功能将无法使用。请在.env文件中设置TAVILY_API_KEY。")
        return
    
    app = create_search_assistant()
    print("🔍 智能搜索助手启动！")
    print("我会使用Tavily API为您搜索最新、最准确的信息")
    print("支持各种问题：新闻、技术、知识问答等")
    print("(输入 'quit' 退出)\n")

    session_count = 0
    while True:
        user_input = input("请输入您的问题: ")
        if user_input.lower() in ['quit', 'q', '退出', 'exit']:
            print("👋 感谢使用智能搜索助手，再见！")
            break
        
        if not user_input:
            print("⚠️ 请输入一个有效的问题。")
            continue

        session_count += 1
        config = {"configurable": {"thread_id": f"search_session_{session_count}"}}

        initial_state = {
            "messages": [HumanMessage(content = user_input)],
            "user_query": user_input,
            "search_query": "",
            "search_results": "",
            "final_answer": "",
            "step": "start",
        }
        try:
            print("\n" + "=" * 60)

            #执行workflow
            async for output in app.astream(initial_state, config=config):
                for node_name, node_output in output.items():
                    if "messages" in node_output and node_output["messages"]:
                        latest_message = node_output["messages"][-1]
                        if isinstance(latest_message, AIMessage):
                            if node_name == "understand":
                                print(f"🧠 理解阶段: {latest_message.content}")
                            elif node_name == "search":
                                print(f"🔍 搜索阶段: {latest_message.content}")
                            elif node_name == "answer":
                                print(f"\n💡 最终回答:\n{latest_message.content}")
            print("\n" + "=" * 60)

        except Exception as e:
            print(f"❌ 处理过程中发生错误: {str(e)}")
            print("请重新输入问题或检查环境配置。")

if __name__ == "__main__":
        asyncio.run(main())