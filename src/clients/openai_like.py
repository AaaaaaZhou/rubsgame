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
        """dev_mode 下打印完整请求到 CLI"""
        _cli_debug(f"\n[LLM DEBUG] {self._model_name}")

        # 打印 messages（脱敏 content 过长部分）
        for i, msg in enumerate(messages):
            role = msg.get("role", "?")
            content = msg.get("content", "")
            if len(content) > 200:
                content = content[:200] + "..."
            name = msg.get("name", "")
            extra = f", name={name}" if name else ""
            _cli_debug(f"  --> messages[{i}]: role={role}{extra}, content={json.dumps(content, ensure_ascii=False)}")

        # 打印请求参数（隐藏 api_key）
        display_params = {k: v for k, v in params.items() if k != "messages"}
        if "api_key" in display_params:
            display_params["api_key"] = "***"
        _cli_debug(f"  --> params: {json.dumps(display_params, ensure_ascii=False, indent=None})")

        req_tokens = self.count_tokens(
            "".join(m.get("content", "") for m in messages)
        )
        _cli_debug(f"  --> request_tokens: ~{req_tokens}")

    def _print_response(
        self,
        content: str,
        params: Dict[str, Any],
        latency: float
    ) -> None:
        """dev_mode 下打印完整响应到 CLI"""
        resp_tokens = self.count_tokens(content)
        display_content = content if len(content) <= 300 else content[:300] + "..."
        _cli_debug(f"  <-- response: {json.dumps(display_content, ensure_ascii=False)}")
        _cli_debug(f"  <-- response_tokens: ~{resp_tokens}, latency: {latency:.2f}s\n")
