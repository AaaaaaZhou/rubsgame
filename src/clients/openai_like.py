"""
OpenAI 兼容客户端
支持 DeepSeek、MiniMax 等 OpenAI API 兼容的模型
通过配置驱动实现平台差异化
"""
import sys
import time
import logging
import json
from typing import Any, Dict, List, Optional

from openai import OpenAI

from .base import BaseLLMClient


def _cli_debug(*args, **kwargs):
    """打印到 CLI（stdout），不受日志级别控制"""
    print(*args, **kwargs)


class LLMDebugFormatter:
    """LLM 通信调试格式化器（仅 dev_mode 启用）"""

    ROLE_COLORS = {
        "system": "\033[34m",    # 蓝色
        "user": "\033[32m",      # 绿色
        "assistant": "\033[33m", # 黄色
        "tool": "\033[31m",      # 红色
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    def format_request(
        self,
        model_name: str,
        messages: List[Dict[str, Any]],
        params: Dict[str, Any],
        tokens: int
    ) -> str:
        """格式化请求输出"""
        lines = []

        # Header
        display_params = {k: v for k, v in params.items() if k != "messages"}
        if "api_key" in display_params:
            display_params["api_key"] = "***"
        params_str = ", ".join(f"{k}={self._format_value(v)}" for k, v in display_params.items())

        lines.append(f"\n{self.BOLD}{self._box_top('Request', model_name)}{self.RESET}")
        lines.append(f"{self.DIM}  Tokens: ~{tokens}{self.RESET}")

        # Messages section
        lines.append(f"{self.BOLD}{self._section('Messages')}{self.RESET}")
        for i, msg in enumerate(messages):
            lines.append(self._format_message(i, msg))

        # Parameters section
        lines.append(f"{self.BOLD}{self._section('Parameters')}{self.RESET}")
        for k, v in display_params.items():
            lines.append(f"  {self._dim(k)}: {self._format_value(v)}")

        lines.append(self._box_bottom())
        return "\n".join(lines) + "\n"

    def format_response(self, content: str, tokens: int, latency: float) -> str:
        """格式化响应输出"""
        lines = []

        lines.append(f"{self.BOLD}{self._box_top('Response', '')}{self.RESET}")
        lines.append(f"{self.DIM}  Tokens: ~{tokens} | Latency: {latency:.2f}s{self.RESET}")

        # Content section
        lines.append(f"{self.BOLD}{self._section('Content')}{self.RESET}")

        # 尝试解析 JSON 并格式化
        try:
            parsed = json.loads(content)
            lines.append(self._format_json_content(parsed))
        except Exception:
            # 非 JSON 时直接显示原文
            display_content = content if len(content) <= 300 else content[:300] + "..."
            lines.append(f"  {display_content}")

        lines.append(self._box_bottom())
        return "\n".join(lines) + "\n"

    def format_tool_call(self, func_name: str, arguments: str) -> str:
        """格式化 tool call 输出"""
        lines = []
        lines.append(f"  {self.BOLD}┌─ Tool: {func_name}{self.RESET}")
        try:
            args = json.loads(arguments)
            for k, v in args.items():
                lines.append(f"  │   {self._dim(k)}: {self._format_value(v)}")
        except Exception:
            lines.append(f"  │   {arguments}")
        lines.append(f"  └─────────────────────────────────")
        return "\n".join(lines) + "\n"

    # ==================== 内部格式化方法 ====================

    def _format_message(self, idx: int, msg: Dict[str, Any]) -> str:
        role = msg.get("role", "?")
        color = self.ROLE_COLORS.get(role, "")
        label = f"[{idx}] {role.upper()}"

        lines = [f"  {color}{self.BOLD}{label}{self.RESET}"]

        # content 字段
        content = msg.get("content", "")
        if content:
            if len(content) > 200:
                lines.append(self._truncate_content(content, 200))
            else:
                lines.append(f"      {content}")

        # tool_calls 嵌套展示
        if "tool_calls" in msg:
            for tc in msg["tool_calls"]:
                func = tc.get("function", {})
                fname = func.get("name", "?")
                fargs = func.get("arguments", "{}")
                lines.append(f"      {self._tool_tree(fname, fargs)}")

        # tool 相关
        if role == "tool":
            tc_id = msg.get("tool_call_id", "")
            lines.append(f"      {self.DIM}tool_call_id: {tc_id}{self.RESET}")

        return "\n".join(lines)

    def _format_json_content(self, parsed: Dict[str, Any], indent: int = 2) -> str:
        """格式化 JSON 内容为多行可读形式"""
        lines = []
        for key, value in parsed.items():
            val_str = self._format_value(value)
            lines.append(f"  {self.BOLD}{key}{self.RESET}: {val_str}")
        return "\n".join(lines)

    def _format_value(self, value: Any, max_len: int = 60) -> str:
        """格式化单个值，过长则截断"""
        if isinstance(value, str):
            if len(value) > max_len:
                return f'"{value[:max_len]}..." ({len(value)} chars)'
            return f'"{value}"'
        elif isinstance(value, (int, float, bool)):
            return str(value)
        elif isinstance(value, list):
            if len(value) > 3:
                return f"[{len(value)} items]"
            return str(value)
        elif isinstance(value, dict):
            return str(value)
        return str(value)

    def _truncate_content(self, content: str, limit: int) -> str:
        """截断长文本，显示前几行"""
        lines = content.split("\n")
        shown = []
        total = 0
        for line in lines:
            total += len(line) + 1
            if total > limit:
                break
            shown.append(line)
        result = "\n".join(shown)
        return f"      {result}\n      {self.DIM}... ({len(content)} chars total){self.RESET}"

    def _tool_tree(self, func_name: str, arguments: str) -> str:
        """格式化 tool call 为树状结构"""
        lines = [f"{self.BOLD}┌─ {func_name}{self.RESET}"]
        try:
            args = json.loads(arguments)
            for i, (k, v) in enumerate(args.items()):
                lines.append(f"│   {self._dim(k)}: {self._format_value(v)}")
        except Exception:
            lines.append(f"│   {arguments}")
        lines.append(f"└─")
        return "\n".join(lines)

    def _section(self, title: str) -> str:
        return f"├─ {title} ─{'─' * 40}"

    def _box_top(self, label: str, model: str) -> str:
        width = 60
        if model:
            return f"┌─ {label} ({model}) {'─' * (width - len(label) - len(model) - 4)}"
        return f"┌─ {label} {'─' * (width - len(label) - 3)}"

    def _box_bottom(self) -> str:
        return "└" + "─" * 61

    def _dim(self, text: str) -> str:
        return f"{self.DIM}{text}{self.RESET}"


# 全局格式化器实例（延迟初始化）
_debug_formatter: Optional[LLMDebugFormatter] = None


def _get_formatter() -> LLMDebugFormatter:
    global _debug_formatter
    if _debug_formatter is None:
        _debug_formatter = LLMDebugFormatter()
    return _debug_formatter


class OpenAILikeClient(BaseLLMClient):
    """OpenAI 兼容客户端

    通过 llm_config.yaml 中的配置差异化为不同平台提供统一接口。
    支持的差异配置项：
    - max_tokens_param: 输出 token 参数名（max_tokens 或 max_completion_tokens）
    - supports_response_format: 是否支持结构化输出
    - response_format: 结构化输出格式配置
    - top_p: 采样参数
    - extra_roles: 支持的特殊 role 类型
    """

    def __init__(
        self,
        model_name: str,
        config: Dict[str, Any],
        logger: Optional[logging.Logger] = None,
        dev_mode: bool = False
    ):
        """初始化 OpenAI 兼容客户端

        Args:
            model_name: 模型名称（如 "deepseek_reasoner"）
            config: 模型配置字典，应包含 api_key、base_url、model 等字段
            logger: 可选的日志记录器
            dev_mode: 是否开启开发模式（打印完整通信详情到 CLI）
        """
        self._model_name = model_name
        self._config = config
        self._dev_mode = dev_mode
        self._logger = logger or logging.getLogger(f"clients.{model_name}")

        self._ensure_api_key(config)

        self._client = OpenAI(
            api_key=config["api_key"],
            base_url=config.get("base_url", "https://api.openai.com/v1")
        )

        self._max_tokens_param = config.get("max_tokens_param", "max_tokens")
        self._supports_response_format = config.get("supports_response_format", False)
        self._default_response_format = config.get("response_format")
        self._top_p = config.get("top_p")
        self._extra_roles = config.get("extra_roles", [])
        self._asset_manager = None

        self._logger.info(
            f"OpenAILikeClient initialized for '{model_name}': "
            f"provider=openai_like, max_tokens_param={self._max_tokens_param}, "
            f"supports_response_format={self._supports_response_format}, "
            f"extra_roles={self._extra_roles}"
        )

    @property
    def model_name(self) -> str:
        return self._model_name

    def chat(
        self,
        messages: List[Dict[str, Any]],
        **kwargs
    ) -> str:
        """发送对话请求"""
        request_params = self._build_base_params(messages, **kwargs)
        start_time = time.time()

        if self._dev_mode:
            self._print_request(messages, request_params)

        try:
            response = self._client.chat.completions.create(**request_params)
            latency = time.time() - start_time
            content = response.choices[0].message.content or ""

            if self._dev_mode:
                self._print_response(content, request_params, latency)

            self._logger.debug(f"chat response: {content[:100]}...")
            return content
        except Exception as e:
            self._logger.error(f"chat request failed: {e}")
            raise

    def chat_structured(
        self,
        messages: List[Dict[str, Any]],
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Any:
        """发送结构化输出请求"""
        if not self._supports_response_format:
            self._logger.warning(
                f"Model '{self._model_name}' does not support structured output, "
                "falling back to regular chat"
            )
            return self.chat(messages, **kwargs)

        format_config = response_format or self._default_response_format
        if not format_config:
            self._logger.warning(
                f"No response_format provided and model has no default, "
                "falling back to regular chat"
            )
            return self.chat(messages, **kwargs)

        request_params = self._build_base_params(messages, **kwargs)
        request_params["response_format"] = format_config
        start_time = time.time()

        if self._dev_mode:
            self._print_request(messages, request_params)

        try:
            response = self._client.chat.completions.create(**request_params)
            latency = time.time() - start_time
            content = response.choices[0].message.content or ""

            if self._dev_mode:
                self._print_response(content, request_params, latency)

            self._logger.debug(f"chat_structured response: {content[:100]}...")
            return content
        except Exception as e:
            self._logger.error(f"chat_structured request failed: {e}")
            raise

    def count_tokens(self, text: str) -> int:
        return len(text) // 4

    def set_asset_manager(self, asset_manager) -> None:
        """设置 asset manager 引用，用于 tool 执行"""
        self._asset_manager = asset_manager

    def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> str:
        """发送对话请求，支持 tool calling"""
        request_params = self._build_base_params(messages, **kwargs)
        if tools:
            request_params["tools"] = tools
        if "tool_choice" not in request_params:
            request_params["tool_choice"] = "auto"

        max_iterations = 10
        iteration = 0

        if self._dev_mode:
            self._print_request(messages, request_params)

        while iteration < max_iterations:
            iteration += 1
            start_time = time.time()
            response = self._client.chat.completions.create(**request_params)
            latency = time.time() - start_time
            message = response.choices[0].message

            if self._dev_mode:
                tokens = self.count_tokens(str(message.content or ""))
                _cli_debug(_get_formatter().format_response(
                    message.content or "", tokens, latency
                ))

            if not message.tool_calls:
                return message.content or ""

            for tool_call in message.tool_calls:
                if self._dev_mode:
                    func = tool_call.function
                    _cli_debug(_get_formatter().format_tool_call(
                        func.name, func.arguments
                    ))
                tool_result = self._execute_tool(tool_call.function, tools)
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": tool_call.id,
                        "type": "function",
                        "function": tool_call.function
                    }]
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result
                })

        raise RuntimeError("Tool calling exceeded max iterations")

    def _execute_tool(
        self,
        function,
        tools: List[Dict[str, Any]]
    ) -> str:
        """根据 function name 执行对应工具"""
        func_name = function.name

        if func_name == "search_world":
            import json
            args = json.loads(function.arguments)
            if self._asset_manager is None:
                return json.dumps({"error": "asset_manager not set"}, ensure_ascii=False)
            result = self._asset_manager.query_world(args.get("keyword", ""))
            return json.dumps(result, ensure_ascii=False)

        self._logger.warning(f"Unknown tool: {func_name}")
        return json.dumps({"error": f"Unknown tool: {func_name}"}, ensure_ascii=False)

    def _build_base_params(
        self,
        messages: List[Dict[str, Any]],
        **kwargs
    ) -> Dict[str, Any]:
        params = {
            "model": self._config["model"],
            "messages": self._filter_messages(messages),
        }

        if self._max_tokens_param == "max_completion_tokens":
            params["max_completion_tokens"] = kwargs.pop(
                "max_tokens",
                self._config.get("max_tokens", 2048)
            )
        else:
            params["max_tokens"] = kwargs.pop(
                "max_tokens",
                self._config.get("max_tokens", 8192)
            )

        params["temperature"] = kwargs.pop(
            "temperature",
            self._config.get("temperature", 0.7)
        )

        if self._top_p is not None or "top_p" in kwargs:
            params["top_p"] = kwargs.pop("top_p", self._top_p)

        params.update(kwargs)

        return params

    def _filter_messages(
        self,
        messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        if not self._extra_roles:
            return messages

        valid_roles = {"system", "user", "assistant"}
        valid_roles.update(self._extra_roles)

        filtered = []
        for msg in messages:
            role = msg.get("role", "")
            if role in valid_roles:
                filtered.append(msg)
            else:
                self._logger.debug(
                    f"Filtered out message with unsupported role '{role}' "
                    f"for model '{self._model_name}'"
                )

        return filtered

    def _print_request(
        self,
        messages: List[Dict[str, Any]],
        params: Dict[str, Any]
    ) -> None:
        """dev_mode 下打印完整请求到 CLI（结构化格式）"""
        if not self._dev_mode:
            return
        tokens = self.count_tokens("".join(m.get("content", "") for m in messages))
        output = _get_formatter().format_request(self._model_name, messages, params, tokens)
        _cli_debug(output)

    def _print_response(
        self,
        content: str,
        params: Dict[str, Any],
        latency: float
    ) -> None:
        """dev_mode 下打印完整响应到 CLI（结构化格式）"""
        if not self._dev_mode:
            return
        tokens = self.count_tokens(content)
        output = _get_formatter().format_response(content, tokens, latency)
        _cli_debug(output)
