from hello_agents import SimpleAgent, HelloAgentsLLM
from dotenv import load_dotenv
import os

load_dotenv()

llm = HelloAgentsLLM(
    model=os.getenv("LLM_MODEL_ID", "qwen3.6-plus"),
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
)

# llm = HelloAgentsLLM(provider="modelscope")

agent = SimpleAgent(
    name = "AI助手",
    llm = llm,
    system_prompt = "你是一个有用的AI助手",
)

response = agent.run("介绍你自己")
print(response)

# 添加工具功能（可选）
from hello_agents.tools import CalculatorTool
calculator = CalculatorTool()
# 需要实现7.4.1的MySimpleAgent进行调用，后续章节会支持此类调用方式
# agent.add_tool(calculator)

# 现在可以使用工具了
response = agent.run("请帮我计算 2 + 3 * 4")
print(response)

# 查看对话历史
print(f"历史消息数: {len(agent.get_history())}")