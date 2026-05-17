from typing import Dict, Any

class ToolExecutor:
    """
    工具执行器类，负责执行工具并返回结果。
    """
    def __init__(self):
        self.tools: Dict[str, Dict[str, Any]] = {}

    def register_tool(self, name: str, description: str, func: callable):
        """
        注册一个工具。
        :param name: 工具名称
        :param description: 工具描述
        :param func: 工具函数
        """
        if name in self.tools:
            raise ValueError(f"工具 '{name}' 已经注册过了。")
        self.tools[name] = {
            "description": description,
            "func": func
        }
        print(f"✅ 工具 '{name}' 注册成功。")

    def getTool(self, name: str) -> callable:
        """
        获取工具信息。
        :param name: 工具名称
        :return: 工具信息字典
        """
        if name not in self.tools:
            raise ValueError(f"工具 '{name}' 未找到。")
        return self.tools.get(name, {}).get("func")
    
    def getAvailableTools(self) -> str:
        """
        获取所有可用工具的名称和描述。
        :return: 工具名称和描述的字典
        """
        return "\n".join([f"-{name}: {info['description']}" for name, info in self.tools.items()])