"""
LLM 客户端抽象基类
定义所有 LLM 客户端必须实现的接口
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type


class BaseLLMClient(ABC):
    """LLM 客户端抽象基类"""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """返回客户端对应的模型名称"""
        pass

    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, Any]],
        **kwargs
    ) -> str:
        """发送对话请求

        Args:
            messages: 消息列表，每条消息为 {"role": str, "content": str, "name"?: str}
            **kwargs: 额外参数，会覆盖默认配置

        Returns:
            模型返回的文本内容
        """
        pass

    @abstractmethod
    def chat_structured(
        self,
        messages: List[Dict[str, Any]],
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Any:
        """发送结构化输出请求

        Args:
            messages: 消息列表
            response_format: 结构化输出格式描述，如 {"type": "json_object"}
            **kwargs: 额外参数

        Returns:
            解析后的结构化对象（具体类型由调用方指定）
        """
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """估算文本的 token 数量

        Args:
            text: 待估算的文本

        Returns:
            估算的 token 数量
        """
        pass

    @abstractmethod
    def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> str:
        """发送对话请求，支持 tool calling

        当 LLM 判断需要调用工具时，自动执行 tool 并将结果注入消息循环，
        直到 LLM 返回最终回复。

        Args:
            messages: 消息列表，每条消息为 {"role": str, "content": str}
            tools: OpenAI 格式的 tool schema 列表
            **kwargs: 额外参数

        Returns:
            模型最终回复文本
        """
        pass

    def _ensure_api_key(self, config: Dict[str, Any]) -> None:
        """检查 API Key 是否配置

        Args:
            config: 模型配置字典

        Raises:
            ValueError: API Key 未配置
        """
        if not config.get("api_key"):
            raise ValueError(
                f"API key not configured for model '{self.model_name}'. "
                "Set it via environment variable or config file."
            )
