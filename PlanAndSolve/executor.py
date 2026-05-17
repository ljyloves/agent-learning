from typing import Dict, Any
from PlanAndSolve.prompts import EXECUTOR_PROMPT_TEMPLATE
from llm_client import HelloAgentsLLM
class Executor:
    def __init__(self, llm_client):
        self.llm_client = llm_client
    
    def execute(self, question: str, plan: list[str]) -> str:
        """执行给定的计划来解决问题。"""
        history = []
        for i, step in enumerate(plan):
            print(f"\n--- 执行步骤 {i+1}/{len(plan)} ---")
            prompt = EXECUTOR_PROMPT_TEMPLATE.format(
                question=question,
                plan=plan,
                history=history if history else "无",
                current_step=step
            )
            messages = [
                {"role": "user", "content": prompt}
            ]
            step_result = self.llm_client.think(messages = messages) or ""
            history += f"\n步骤 {i+1}: {step}\n结果: {step_result}"
            print(f"步骤结果: {step_result}")
        final_answer = step_result
        return final_answer