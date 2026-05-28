from typing import Optional, Iterator
from hello_agents import SimpleAgent, HelloAgentsLLM, Config, Message
import re
import json


class MySimpleAgent(SimpleAgent):
    """
    重写的简单对话Agent
    展示如何基于框架基类构建自定义Agent
    """

    def __init__(
        self,
        name: str,
        llm: HelloAgentsLLM,
        system_prompt: Optional[str] = None,
        config: Optional[Config] = None,
        tool_registry: Optional["ToolRegistry"] = None,
        enable_tool_calling: bool = True,
    ):
        super().__init__(name, llm, system_prompt, config)
        self.tool_registry = tool_registry
        self.enable_tool_calling = enable_tool_calling and tool_registry is not None
        print(
            f"✅ {name} 初始化完成，工具调用: {'启用' if self.enable_tool_calling else '禁用'}"
        )

    def run(self, input_text: str, max_tool_iterations: int = 3, **kwargs) -> str:
        """
        重写的运行方法 - 实现简单对话逻辑，支持可选工具调用
        """
        print(f"🤖 {self.name} 正在处理: {input_text}")

        # 构建消息列表
        messages = []

        # 添加系统消息
        enhanced_system_prompt = self._get_enhanced_system_prompt()
        messages.append({"role": "system", "content": enhanced_system_prompt})

        # 添加历史消息
        for msg in self._history:
            messages.append({"role": "system", "content": enhanced_system_prompt})

        # 添加当前用户消息
        messages.append({"role": "user", "content": input_text})

        if not self.enable_tool_calling:
            response = self.llm.invoke(messages, **kwargs)
            self.add_message(Message(input_text, "user"))
            self.add_message(Message(response, "assistant"))
            print(f"✅ {self.name} 响应完成")
            return response

        return self._run_with_tools(messages, input_text, max_tool_iterations, **kwargs)

    def _get_enhanced_system_prompt(self) -> str:
        """
        构建增强的系统提示词，包含工具信息
        """
        base_prompt = self.system_prompt or "你是一个有用的AI助手。"

        if not self.enable_tool_calling or not self.tool_registry:
            return base_prompt

        tools_description = self.tool_registry.get_tools_description()
        if not tools_description or tools_description == "暂无可用工具":
            return base_prompt

        tools_section = "\n\n## 可用工具\n"
        tools_section += "你可以使用以下工具来帮助回答问题:\n"
        tools_section += tools_description + "\n"

        tools_section += "\n## 工具调用格式\n"
        tools_section += "当需要使用工具时，请使用以下格式:\n"
        tools_section += "`[TOOL_CALL:{tool_name}:{parameters}]`\n"
        tools_section += "例如:`[TOOL_CALL:search:Python编程]` 或 `[TOOL_CALL:memory:recall=用户信息]`\n\n"
        tools_section += (
            "工具调用结果会自动插入到对话中，然后你可以基于结果继续回答。\n"
        )

        return base_prompt + tools_section

    def _run_with_tools(
        self, messages: list, input_text: str, max_tool_iterations: int, **kwargs
    ) -> str:
        """
        支持工具调用的运行逻辑
        """
        current_iteration = 0
        final_response = ""

        while current_iteration < max_tool_iterations:
            response = self.llm.invoke(messages, **kwargs)
            tools_calls = self._parse_tool_calls(response)
            if tools_calls:
                print(f"🔧 检测到 {len(tools_calls)} 个工具调用")
                # 执行所有工具调用并收集结果
                tool_results = []
                clean_response = response

                for call in tools_calls:
                    result = self._execute_tool_call(
                        call["tool_name"], call["parameters"]
                    )
                    tool_results.append(result)
                    # 从响应中移除工具调用标记
                    clean_response = clean_response.replace(call["original"], "")

                # 构建包含工具结果的消息
                messages.append({"role": "assistant", "content": clean_response})

                # 添加工具结果
                tool_results_text = "\n\n".join(tool_results)
                messages.append(
                    {
                        "role": "user",
                        "content": f"工具执行结果:\n{tool_results_text}\n\n请基于这些结果给出完整的回答。",
                    }
                )
                current_iteration += 1
                continue
            final_response = response
            break

        if current_iteration >= max_tool_iterations and not final_response:
            final_response = self.llm.invoke(messages, **kwargs)
        # 保存到历史记录
        self.add_message(Message(input_text, "user"))
        self.add_message(Message(final_response, "assistant"))
        print(f"✅ {self.name} 响应完成")

        return final_response

    def _parse_tool_calls(self, text: str) -> list:
        """
        解析文本中的工具调用
        """
        pattern = r"\[TOOL_CALL:([^:]+):([^\]]+)\]"
        matches = re.findall(pattern, text)

        tool_calls = []
        for tool_name, parameters in matches:
            tool_calls.append(
                {
                    "tool_name": tool_name.strip(),
                    "parameters": parameters.strip(),
                    "original": f"[TOOL_CALL:{tool_name}:{parameters}]",
                }
            )
        return tool_calls

    def _execute_tool_call(self, tool_name: str, parameters: str) -> str:
        """执行工具调用"""
        if not self.tool_registry:
            return "❌ 错误:未配置工具注册表"

        try:
            # 智能参数解析
            if tool_name == "calculator":
                # 计算器工具直接传入表达式
                result = self.tool_registry.execute_tool(tool_name, parameters)
            else:
                # 其他工具使用智能参数解析
                param_dict = self._parse_tool_parameters(tool_name, parameters)
                tool = self.tool_registry.get_tool(tool_name)
                if not tool:
                    return f"❌ 错误:未找到工具 '{tool_name}'"
                result = tool.run(param_dict)

            return f"🔧 工具 {tool_name} 执行结果:\n{result}"
        except Exception as e:
            return f"❌ 工具调用失败:{str(e)}"

    def _parse_tool_parameters(self, tool_name: str, parameters: str) -> dict:
        """解析工具参数并返回字典形式。"""
        raw = parameters.strip()
        if not raw:
            return {}

        # 尝试 JSON 解析，优先支持标准 JSON 参数
        if raw.startswith("{") or raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
                return {"input": parsed}
            except json.JSONDecodeError:
                pass

        # 解析 key=value 对，支持逗号、分号、空格分隔
        param_pattern = r"([\w\-]+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^,;]+))"
        matches = re.finditer(param_pattern, raw)
        params = {}
        for match in matches:
            key = match.group(1)
            value = match.group(2) or match.group(3) or match.group(4) or ""
            params[key] = value.strip()

        if params:
            return params

        # 解析简单的键值对列表，例如 key1:value1,key2:value2
        if ":" in raw and ("," in raw or ";" in raw):
            items = re.split(r"[;,]", raw)
            for item in items:
                item = item.strip()
                if not item:
                    continue
                parts = item.split(":", 1)
                if len(parts) == 2:
                    params[parts[0].strip()] = parts[1].strip()
            if params:
                return params

        # 如果没有解析出结构化参数，则将整个字符串作为单个输入参数
        return {"input": raw}

    def stream_run(self, input_text: str, **kwargs) -> Iterator[str]:
        """
        自定义的流式运行方法
        """
        print(f"🌊 {self.name} 开始流式处理: {input_text}")

        messages = []

        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        for msg in self._history:
            messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": input_text})

        # 流式调用LLM
        full_response = ""
        print("📝 实时响应: ", end="")
        for chunk in self.llm.stream_invoke(messages, **kwargs):
            full_response += chunk
            print(chunk, end="", flush=True)
            yield chunk

        print()  # 换行

        # 保存完整对话到历史记录
        self.add_message(Message(input_text, "user"))
        self.add_message(Message(full_response, "assistant"))
        print(f"✅ {self.name} 流式响应完成")

    def add_tool(self, tool) -> None:
        """添加工具到 Agent（便利方法）。"""
        if not self.tool_registry:
            from hello_agents import ToolRegistry

            self.tool_registry = ToolRegistry()
            self.enable_tool_calling = True

        self.tool_registry.register_tool(tool)
        print(f"🔧 工具 '{tool.name}' 已添加")

    def has_tools(self) -> bool:
        """检查是否有可用工具。"""
        return self.enable_tool_calling and self.tool_registry is not None

    def remove_tool(self, tool_name: str) -> bool:
        """移除工具（便利方法）"""
        if self.tool_registry:
            self.tool_registry.unregister(tool_name)
            return True
        return False

    def list_tools(self) -> list:
        """列出所有可用工具。"""
        if self.tool_registry:
            return self.tool_registry.list_tools()
        return []
