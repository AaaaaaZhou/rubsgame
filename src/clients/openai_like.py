"""
OpenAI 兼容客户端
支持 DeepSeek、MiniMax 等 OpenAI API 兼容的模型
通过配置驱动实现平台差异化
"""
import logging
from typing import Any, Dict, List, Optional

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from .base import BaseLLMClient


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
        logger: Optional[logging.Logger] = None
    ):
        """初始化 OpenAI 兼容客户端

        Args:
            model_name: 模型名称（如 "deepseek_reasoner"）
            config: 模型配置字典，应包含 api_key、base_url、model 等字段
            logger: 可选的日志记录器
        """
        self._model_name = model_name
        self._config = config
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

        try:
            response = self._client.chat.completions.create(**request_params)
            content = response.choices[0].message.content
            self._logger.debug(f"chat response: {content[:100]}...")
            return content or ""
        except Exception as e:
            self._logger.error(f"chat request failed: {e}")
            raise

    def chat_structured(
        self,
        messages: List[Dict[str, Any]],
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Any:
        """发送结构化输出请求

        Args:
            messages: 消息列表
            response_format: 结构化输出格式，如 {"type": "json_object"}
                              如果为 None，使用模型默认配置
            **kwargs: 额外参数

        Returns:
            解析后的文本（调用方需自行 JSON 解析）
        """
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

        try:
            response = self._client.chat.completions.create(**request_params)
            content = response.choices[0].message.content
            self._logger.debug(f"chat_structured response: {content[:100]}...")
            return content or ""
        except Exception as e:
            self._logger.error(f"chat_structured request failed: {e}")
            raise

    def count_tokens(self, text: str) -> int:
        """估算 token 数量（简单字符估算）

        精确的 token 计数需要使用 tiktoken 等库，
        此处使用简化估算：约 4 字符 = 1 token

        Args:
            text: 待估算文本

        Returns:
            估算的 token 数量
        """
        return len(text) // 4

    def _build_base_params(
        self,
        messages: List[Dict[str, Any]],
        **kwargs
    ) -> Dict[str, Any]:
        """构建请求参数

        Args:
            messages: 消息列表
            **kwargs: 额外参数会覆盖默认配置

        Returns:
            完整的请求参数字典
        """
        params = {
            "model": self._config["model"],
            "messages": self._filter_messages(messages),
        }

        # 处理输出 token 数量参数（差异化配置）
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

        # 处理 temperature
        params["temperature"] = kwargs.pop(
            "temperature",
            self._config.get("temperature", 0.7)
        )

        # 处理 top_p（部分模型需要）
        if self._top_p is not None or "top_p" in kwargs:
            params["top_p"] = kwargs.pop("top_p", self._top_p)

        # 合并额外参数
        params.update(kwargs)

        return params

    def _filter_messages(
        self,
        messages: List[Dict[str, Any]]
    ) -> List[ChatCompletionMessageParam]:
        """过滤消息，移除不支持的 role 类型

        Args:
            messages: 原始消息列表

        Returns:
            过滤后的消息列表
        """
        if not self._extra_roles:
            return messages  # 不过滤

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
