import os
import asyncio
from dotenv import load_dotenv

from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.ui import Console

load_dotenv()  # 加载环境变量


def create_model_client():
    """创建一个模型客户端（使用仓库内的 HelloAgentsLLM）。"""
    return OpenAIChatCompletionClient(
        model=os.getenv("LLM_MODEL_ID", "qwen3.6-plus"),
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv(
            "LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
        ),
        model_info={
            "function_calling": True,
            "max_tokens": 4096,
            "context_length": 32768,
            "vision": False,
            "json_output": True,
            "family": "qwen",
            "structured_output": True,
        },
    )


def create_product_manager(model_client):
    """创建一个产品经理Agent"""
    system_message = """你是一位经验丰富的产品经理，专门负责软件产品的需求分析和项目规划。

你的核心职责包括：
1. **需求分析**：深入理解用户需求，识别核心功能和边界条件
2. **技术规划**：基于需求制定清晰的技术实现路径
3. **风险评估**：识别潜在的技术风险和用户体验问题
4. **协调沟通**：与工程师和其他团队成员进行有效沟通

当接到开发任务时，请按以下结构进行分析：
1. 需求理解与分析
2. 功能模块划分
3. 技术选型建议
4. 实现优先级排序
5. 验收标准定义

请简洁明了地回应，并在分析完成后说"请工程师开始实现"。"""
    return AssistantAgent(
        name="product_manager", model_client=model_client, system_message=system_message
    )


def create_software_engineer(model_client):
    """创建一个软件工程师Agent"""
    system_message = """你是一位资深的软件工程师，擅长 Python 开发和 Web 应用构建。

你的技术专长包括：
1. **Python 编程**：熟练掌握 Python 语法和最佳实践
2. **Web 开发**：精通 Streamlit、Flask、Django 等框架
3. **API 集成**：有丰富的第三方 API 集成经验
4. **错误处理**：注重代码的健壮性和异常处理

当收到开发任务时，请：
1. 仔细分析技术需求
2. 选择合适的技术方案
3. 编写完整的代码实现
4. 添加必要的注释和说明
5. 考虑边界情况和异常处理

请提供完整的可运行代码，并在完成后说"请代码审查员检查"。"""
    return AssistantAgent(
        name="software_engineer",
        model_client=model_client,
        system_message=system_message,
    )


def create_code_reviewer(model_client):
    """创建一个代码审查员Agent"""
    system_message = """你是一位经验丰富的代码审查专家，专注于代码质量和最佳实践。

你的审查重点包括：
1. **代码质量**：检查代码的可读性、可维护性和性能
2. **安全性**：识别潜在的安全漏洞和风险点
3. **最佳实践**：确保代码遵循行业标准和最佳实践
4. **错误处理**：验证异常处理的完整性和合理性

审查流程：
1. 仔细阅读和理解代码逻辑
2. 检查代码规范和最佳实践
3. 识别潜在问题和改进点
4. 提供具体的修改建议
5. 评估代码的整体质量

请提供具体的审查意见，完成后说"代码审查完成，请测试工程师测试"。"""
    return AssistantAgent(
        name="code_reviewer", model_client=model_client, system_message=system_message
    )


def create_quality_assurance(model_client):
    """创建一个测试工程师Agent"""
    system_message = """你是一位严谨的测试工程师（QA），专注于软件质量保障和缺陷发现。

你的核心职责包括：
1. **测试规划**：根据需求文档设计全面的测试用例
2. **功能测试**：验证所有功能是否按预期工作
3. **边界测试**：检查极端情况和异常输入的处理
4. **兼容性测试**：验证不同环境和条件下的运行表现
5. **缺陷报告**：清晰记录发现的问题并给出优先级

测试流程：
1. 仔细阅读需求文档和代码实现
2. 设计测试用例（正常流程 + 异常流程）
3. 逐项验证功能是否符合验收标准
4. 记录发现的问题和改进建议
5. 给出最终的质量评估结论

请提供结构化的测试报告，完成后说"测试完成，请用户代理验证"。 """
    return AssistantAgent(
        name="quality_assurance",
        model_client=model_client,
        system_message=system_message,
    )


def create_user_proxy(model_client):
    """创建一个用户代理，模拟最终用户的反馈和测试"""

    # Provide a simple non-interactive input function that returns TERMINATE
    def _auto_input(prompt: str) -> str:
        return "TERMINATE"

    return UserProxyAgent(
        name="user_proxy",
        description="""用户代理，负责以下职责：
1. 代表用户提出开发需求
2. 执行最终的代码实现
3. 验证功能是否符合预期
4. 提供用户反馈和建议

完成测试后请回复 TERMINATE。""",
        input_func=_auto_input,
    )


async def run_software_team():
    """运行软件开发团队的协作流程"""
    print("🚀 正在启动软件开发团队...")
    model_client = create_model_client()
    print("正在创建团队成员...")
    product_manager = create_product_manager(model_client)
    software_engineer = create_software_engineer(model_client)
    code_reviewer = create_code_reviewer(model_client)
    quality_assurance = create_quality_assurance(model_client)
    user_proxy = create_user_proxy(model_client)

    termination = TextMentionTermination("TERMINATE")

    team_chat = RoundRobinGroupChat(
        participants=[
            product_manager,
            software_engineer,
            code_reviewer,
            quality_assurance,
            user_proxy,
        ],
        termination_condition=termination,
        max_turns=20,
    )

    task = """我们需要开发一个比特币价格显示应用，具体要求如下：

核心功能：
- 实时显示比特币当前价格（USD）
- 显示24小时价格变化趋势（涨跌幅和涨跌额）
- 提供价格刷新功能

技术要求：
- 使用 Streamlit 框架创建 Web 应用
- 界面简洁美观，用户友好
- 添加适当的错误处理和加载状态

请团队协作完成这个任务，从需求分析到最终实现。"""

    print("团队正在协作开发...")
    result = await Console(team_chat.run_stream(task=task))

    print("\n" + "=" * 60)
    print("✅ 团队协作完成！")

    return result


if __name__ == "__main__":
    try:
        result = asyncio.run(run_software_team())
        print("\n📋 协作结果摘要：")
        print("- 参与智能体数量：5个")
        print(f"- 任务完成状态：{'成功' if result else '需要进一步处理'}")
    except ValueError as e:
        print(f"❌ 值错误: {e}")
        print("请检查环境变量配置，确保模型ID、API密钥和服务地址正确设置。")
    except Exception as e:
        print(f"❌ 发生未知错误: {e}")
        print("请检查错误信息并尝试解决。")
        import traceback

        traceback.print_exc()
