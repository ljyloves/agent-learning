from Reflection.memory import Memory
from Reflection.prompts import INITIAL_PROMPT_TEMPLATE, REFINE_PROMPT_TEMPLATE, REFLECT_PROMPT_TEMPLATE


class ReflectionAgent:
    def __init__(self, llm_client, max_interactions=3):
        self.llm_client = llm_client
        self.memory = Memory()
        self.max_interactions = max_interactions

    def run(self, task):
        print(f"开始处理任务: {task}")
        initial_prompt = INITIAL_PROMPT_TEMPLATE.format(task=task)
        initial_code = self._get_llm_response(initial_prompt)
        self.memory.add_record("execution", initial_code)

        for i in range(self.max_interactions):
            print(f"\n=== 评审轮次 {i+1} ===")

            # 反思
            last_code = self.memory.get_last_execution()
            reflection_prompt = REFLECT_PROMPT_TEMPLATE.format(task=task, code=last_code)
            feedback = self._get_llm_response(reflection_prompt)
            self.memory.add_record("reflection", feedback)

            if "最终答案" in feedback:
                print("评审员已经给出了最终答案，结束对话。")
                break

            #优化
            improvement_prompt = REFINE_PROMPT_TEMPLATE.format(
                task=task,
                last_code_attempt=last_code,
                feedback=feedback
            )
            improved_code = self._get_llm_response(improvement_prompt)
            self.memory.add_record("execution", improved_code)
            
        final_code = self.memory.get_last_execution()
        print(f"\n--- 任务完成 ---\n最终生成的代码:\n```python\n{final_code}\n```")
        return final_code

    def _get_llm_response(self, prompt) -> str:
        messages = [{"role": "user", "content": prompt}]
        response = self.llm_client.think(messages=messages)
        return response or ""