# test_reflection_agent.py
from dotenv import load_dotenv
from hello_agents import HelloAgentsLLM, ReflectionAgent

code_prompts = {
    # 1. 专家角色（负责写出高可读性、高覆盖率的初始代码）
    "initial": (
        "你是一位大厂资深的 Python 首席架构师。请针对以下任务编写高质量、符合 PEP 8 规范的 Python 函数。\n\n"
        "【开发任务】:\n{task}\n\n"
        "【硬性要求】:\n"
        "1. 代码必须具备极高的可读性，包含详尽的 Docstring、类型提示（Type Hints）以及关键逻辑注释。\n"
        "2. 充分考虑边界条件（如空值、极端输入）并加入完善的异常处理机制。\n"
        "3. 只输出标准的 Python 代码块，不要包含任何多余的解释说明。"
    ),
    # 2. 深度审查（强迫大模型启动多维度的 Reflection 反思，类似 Code Review 专家）
    "reflect": (
        "你现在扮演严苛的顶级代码评审专家（Code Reviewer）。请对以下编写的代码进行深度审计与反思。\n\n"
        "【原始任务】:\n{task}\n"
        "【待审代码】:\n{content}\n\n"
        "请严格从以下四个维度进行审查，并输出一份结构化的【评审报告】:\n"
        "1. 算法与时间/空间复杂度分析（是否有更优的 $O(n)$ 或 $O(1)$ 解法？是否存在不必要的嵌套循环或内存开销？）\n"
        "2. 代码健壮性与边界漏洞（大数溢出、空输入、非法类型是否会导致程序崩溃？）\n"
        "3. Pythonic 规范（是否善用了生成器、内置函数或标准库？是否符合 Python 的优雅美学？）\n"
        "4. 最终裁决：[通过] 或 [需要优化]（如果需要优化，请给出具体而精准的改进建议）。"
    ),
    # 3. 精英重构（接收硬核反馈，进行像素级的代码优化）
    "refine": (
        "你现在是精益求精的 Python 代码重构大师。请结合专家的深度审查反馈，对初始代码进行像素级的重构优化。\n\n"
        "【原始任务】:\n{task}\n"
        "【专业审查反馈】:\n{feedback}\n\n"
        "【重构目标】:\n"
        "1. 彻底解决反馈中提到的所有复杂度、健壮性以及规范问题。\n"
        "2. 如果反馈意见无需优化，请保持原代码并进行微调。\n"
        "3. 保持原有函数的接口签名不变。\n"
        "4. 最终只输出优化后的纯净 Python 代码块，拒绝任何啰嗦的解释。"
    ),
}

load_dotenv()
llm = HelloAgentsLLM()

general_agent = ReflectionAgent(
    name="我的贾维斯",
    llm=llm,
    max_iterations=2,
    custom_prompts=code_prompts,
)

input_txt = "给你链表的头节点 head ，每 k 个节点一组进行翻转，请你返回修改后的链表。k 是一个正整数，它的值小于或等于链表的长度。如果节点总数不是 k 的整数倍，那么请将最后剩余的节点保持原有顺序。你不能只是单纯的改变节点内部的值，而是需要实际进行节点交换。"
result = general_agent.run(input_txt)
print(f"最终结果:{result}")
