import ast
from llm_client import HelloAgentsLLM
from PlanAndSolve.prompts import PLANNER_PROMPT_TEMPLATE

class Planner:
    def __init__(self, llm_client = None):
        self.llm_client = llm_client or HelloAgentsLLM()

    def plan(self, question: str) -> list[str]:
        """根据问题生成一个解决问题的计划（步骤列表）。"""
        prompt = PLANNER_PROMPT_TEMPLATE.format(question=question)
        messages = [
            {"role": "user", "content": prompt}
        ]
        print("正在生成计划...")
        response_txt = self.llm_client.think(messages = messages)
        try:
            plan_str = response_txt.split("```python")[1].split("```")[0].strip()
            plan = ast.literal_eval(plan_str)
            return plan if isinstance(plan, list) else []
        except (ValueError, SyntaxError, IndexError) as e:
            print(f"解析计划时发生错误: {e}")
            print(f"LLM响应: {response_txt}")
            return []
        except Exception as e:
            print(f"未知错误: {e}")
            return []