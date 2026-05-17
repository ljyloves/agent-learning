import json
import re
from llm_client import HelloAgentsLLM
from ReAct.executor import ToolExecutor
from ReAct.prompts import REACT_PROMPT_TEMPLATE


class ReActAgent:
    def __init__(self, llm_client: HelloAgentsLLM, tool_executor: ToolExecutor, max_steps: int = 5):
        self.llm_client = llm_client
        self.tool_executor = tool_executor
        self.max_steps = max_steps

    def run(self, question: str) -> str:
        """运行ReAct Agent来回答用户的问题。"""
        current_step = 0

        prompt = REACT_PROMPT_TEMPLATE.format(question=question)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": question}
        ]

        tools_schema = self.tool_executor.get_openai_functions()

        while current_step < self.max_steps:
            current_step += 1
            print(f"\n--- 第 {current_step} 步 ---")

            response = self.llm_client.think(messages = messages, tools_schema = tools_schema)
            if not response:
                print("LLM没有返回响应，结束对话。")
                break

            if not getattr(response, "tool_calls", None):
                final_answer = response.content
                print(f"LLM没有提出任何工具调用，认为已经得出最终答案:{final_answer}")
                return final_answer

            messages.append(response)
            tool_call = response.tool_calls[0]  # 目前只处理第一个工具调用
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)
            print(f"LLM提出工具调用: {tool_name}，参数: {tool_args}")

            tool_func = self.tool_executor.getTool(tool_name)
            if not tool_func:
                observation = f"工具 '{tool_name}' 未找到。"
            else:
                try:
                    observation = str(tool_func(**tool_args))
                except Exception as e:
                    observation = f"执行工具 '{tool_name}' 时发生错误: {e}"
            print(f"工具执行结果: {observation}")
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": tool_name,
                "content": observation
            })

        print("达到最大步骤数，结束对话。")
        return None