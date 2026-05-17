from PlanAndSolve.executor import Executor
from PlanAndSolve.planner import Planner


class PlanAndSolveAgent:
    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.planner = Planner(llm_client)
        self.executor = Executor(llm_client)

    def run(self, question: str):
        """运行Plan-and-Solve Agent来回答用户的问题。"""
        print("正在生成解决问题的计划...")
        plan = self.planner.plan(question)
        if not plan:
            print("未能生成有效的计划，结束对话。")
            return "抱歉，我无法为这个问题生成一个解决方案。"

        print("计划生成成功，正在执行计划...")
        final_answer = self.executor.execute(question, plan)
        print(f"计划执行完成。最终答案: {final_answer}")