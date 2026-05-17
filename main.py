import os

from llm_client import HelloAgentsLLM
from dotenv import load_dotenv
from tools import  search

from ReAct.executor import ToolExecutor
from ReAct.agent import ReActAgent

from PlanAndSolve.planner import Planner
from PlanAndSolve.executor import Executor

from Reflection.ReflectionAgent import ReflectionAgent
from Reflection.memory import Memory

# 加载 .env 文件中的环境变量
load_dotenv()

def demo1():
    try:
        llmClient = HelloAgentsLLM()
        
        exampleMessages = [
            {"role": "system", "content": "You are a helpful assistant that writes Python code."},
            {"role": "user", "content": "写一个快速排序算法"}
        ]
        
        print("--- 调用LLM ---")
        responseText = llmClient.think(exampleMessages)
        if responseText:
            print("\n\n--- 完整模型响应 ---")
            print(responseText)
    except ValueError as e:
        print(e)

def demo2():
    try:
        toolExecutor = ToolExecutor()
        toolExecutor.register_tool("search", "使用SerpAPI进行网络搜索", search)
        
        print("\n--- 可用工具 ---")
        print(toolExecutor.getAvailableTools())
        
        print("\n--- 执行 Action ---")
        tool_name = "search"
        tool_input = "明天成都的天气怎么样？"
        toll_func = toolExecutor.getTool(tool_name)
        if toll_func:
            result = toll_func(tool_input)
            print("\n--- 搜索结果 ---")
            print(result)
        else:
            print(f"工具 '{tool_name}' 未找到。")
    except ValueError as e:
        print(e)

def demo_react():
    llmClient = HelloAgentsLLM()
    toolExecutor = ToolExecutor()
    toolExecutor.register_tool(
        name = "search", 
        description = "使用SerpAPI进行网络搜索", 
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "要搜索的关键词"
                }
            },
            "required": ["query"]
        },
        func = search)

    agent = ReActAgent(llm_client=llmClient, tool_executor=toolExecutor, max_steps=5)
    question = "截至2026年5月，中国票房最高的男演员是谁？"
    print(f"用户问题: {question}")
    final_answer = agent.run(question)
    print("\n================ 最终答案 ================")
    print(f"最终答案: {final_answer}")

def demo_plan_and_solve():

    llmClient = HelloAgentsLLM()
    planner = Planner(llm_client=llmClient)
    executor = Executor(llm_client=llmClient)

    question = "问题: 一个水果店周一卖出了15个苹果。周二卖出的苹果数量是周一的两倍。周三卖出的数量比周二少了5个。请问这三天总共卖出了多少个苹果？"
    print(f"用户问题: {question}")

    plan = planner.plan(question)
    print("\n--- 生成的计划 ---")
    for i, step in enumerate(plan):
        print(f"{i+1}. {step}")

    final_answer = executor.execute(question, plan)
    print("\n================ 最终答案 ================")
    print(f"最终答案: {final_answer}")

def demo_reflection():
    llmClient = HelloAgentsLLM()
    agent = ReflectionAgent(llm_client=llmClient, max_interactions=3)

    task = "给定一个二叉树 root ，返回其最大深度。（二叉树的 最大深度 是指从根节点到最远叶子节点的最长路径上的节点数。）"
    final_code = agent.run(task)
    print("\n================ 最终代码 ================")
    print(f"最终生成的代码:\n```python\n{final_code}\n```")
    
if __name__ == '__main__':
    # demo1()
    # demo2()
    demo_react()
    # demo_plan_and_solve()
    # demo_reflection()