from typing import Any, Dict, List
from toolchain import Toolchain
from registry import ToolRegistry


class ToolChainManager:
    """工具链管理器"""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.chains: Dict[str, Toolchain] = {}

    def register_chain(self, chain: Toolchain):
        """注册工具链"""
        self.chains[chain.name] = chain
        print(f"✅ 工具链 '{chain.name}' 已注册")

    def execute_chain(
        self, chain_name: str, input_data: str, context: Dict[str, Any] = None
    ) -> str:
        """执行指定的工具链"""
        if chain_name not in self.chains:
            return f"❌ 工具链 '{chain_name}' 不存在"

        chain = self.chains[chain_name]
        return chain.execute(self.registry, input_data, context)

    def list_chains(self) -> List[str]:
        """列出所有工具链"""
        return list(self.chains.keys())


def create_research_chain() -> Toolchain:
    """创建一个研究工具链:搜索 -> 计算 -> 总结"""
    chain = Toolchain(
        name="research_and_calculate", description="搜索信息并进行相关计算"
    )

    # 步骤1:搜索信息
    chain.add_step(
        tool_name="search", input_template="{input}", output_key="search_result"
    )

    # 步骤2:基于搜索结果进行计算（如果需要）
    chain.add_step(
        tool_name="my_calculator",
        input_template="根据以下信息计算相关数值:{search_result}",
        output_key="calculation_result",
    )

    return chain
