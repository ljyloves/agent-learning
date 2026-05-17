import re
from llm_client import HelloAgentsLLM
from ReAct.executor import ToolExecutor
from ReAct.prompts import REACT_PROMPT_TEMPLATE


class ReActAgent:
    def __init__(self, llm_client: HelloAgentsLLM, tool_executor: ToolExecutor, max_steps: int = 5):
        self.llm_client = llm_client
        self.tool_executor = tool_executor
        self.max_steps = max_steps
        self.history = []

    def run(self, question: str) -> str:
        """运行ReAct Agent来回答用户的问题。"""
        self.history = []
        current_step = 0

        while current_step < self.max_steps:
            current_step += 1
            print(f"\n--- 第 {current_step} 步 ---")

            tools_description = self.tool_executor.getAvailableTools()
            history_str = "\n".join(self.history)
            prompt = REACT_PROMPT_TEMPLATE.format(
                tools=tools_description,
                question=question,
                history=history_str
            )

            messages = [
                {"role": "user", "content": prompt}
            ]
            response_txt = self.llm_client.think(messages = messages)
            if not response_txt:
                print("LLM没有返回响应，结束对话。")
                break

            thought, action = self._parse_output(response_txt)
            if thought:
                print(f"💭 思考: {thought}")
            if not action:
                print("没有检测到Action，结束对话。")
                break
            if action.startswith("Finish"):
                final_answer = re.search(r"Finish\[(.*)\]", action).group(1)
                print(f"✅ 最终答案: {final_answer}")
                return final_answer

            tool_name, tool_input = self._parse_action(action)
            if not tool_name or not tool_input:
                print("无法解析Action，结束对话。")
                continue
            print(f"🔧 执行工具: {tool_name}，输入: {tool_input}")
            tool_func = self.tool_executor.getTool(tool_name)
            if not tool_func:
                observation = f"工具 '{tool_name}' 未找到。"
            else:
                observation = tool_func(tool_input)
            print(f"📊 观察结果: {observation}")

            self.history.append(f"Action: {action}")
            self.history.append(f"Observation: {observation}")

        print("达到最大步骤数，结束对话。")
        return None


    def _parse_output(self, text: str):
        """解析LLM的输出，提取Action和Action Input。"""
        thought_match = re.search(r"Thought:\s*(.*?)(?=\nAction:|$)", text, re.DOTALL)
        action_match = re.search(r"Action:\s*(.*?)(?=\nAction Input:|$)", text, re.DOTALL)

        thought = thought_match.group(1).strip() if thought_match else None
        action = action_match.group(1).strip() if action_match else None

        return thought, action
    
    def _parse_action(self, action: str):
        match = re.match(r"(\w+)\[(.*)\]", action, re.DOTALL)
        if match:
            return match.group(1), match.group(2)
        return None, None