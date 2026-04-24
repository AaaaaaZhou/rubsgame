"""
LLM 客户端管理器
负责根据配置创建、管理 LLM 客户端实例
"""
import logging
from typing import Dict, Optional

from ..utils.config import AppConfig
from .base import BaseLLMClient
from .openai_like import OpenAILikeClient


class ClientManager:
    """LLM 客户端管理器

    根据模型配置动态创建客户端实例，支持多模型切换。
    使用单例模式，确保同一模型的客户端实例复用。
    """

    _instance: Optional["ClientManager"] = None

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        logger: Optional[logging.Logger] = None
    ):
        """初始化客户端管理器

        Args:
            config: 应用配置实例，如果为 None 则使用全局 config
            logger: 可选的日志记录器
        """
        if ClientManager._instance is not None:
            raise RuntimeError(
                "ClientManager is a singleton. Use get_instance() instead."
            )

        self._config = config
        self._logger = logger or logging.getLogger("clients.manager")
        self._clients: Dict[str, BaseLLMClient] = {}

        ClientManager._instance = self
        self._logger.info("ClientManager initialized")

    @classmethod
    def get_instance(cls) -> "ClientManager":
        """获取单例实例

        Returns:
            ClientManager 单例实例
        """
        if cls._instance is None:
            from ..utils.config import config
            cls(config=config)
        return cls._instance

    def get_client(
        self,
        model_name: Optional[str] = None
    ) -> BaseLLMClient:
        """获取指定模型的客户端实例

        Args:
            model_name: 模型名称，如果为 None 则使用默认模型

        Returns:
            LLM 客户端实例

        Raises:
            ValueError: 指定模型不存在
        """
        config = self._get_config()

        if model_name is None:
            model_name = config.current_llm_model

        # 返回缓存的客户端
        if model_name in self._clients:
            return self._clients[model_name]

        # 创建新客户端
        model_config = config.get_llm_config(model_name)
        if not model_config:
            raise ValueError(f"Model '{model_name}' not found in configuration")

        provider = model_config.get("provider", "openai_like")

        if provider == "openai_like":
            client = OpenAILikeClient(
                model_name,
                model_config,
                self._logger,
                dev_mode=self._get_config().dev_mode
            )
        else:
            raise ValueError(
                f"Unsupported provider '{provider}' for model '{model_name}'"
            )

        self._clients[model_name] = client
        self._logger.info(f"Created new client for model '{model_name}'")
        return client

    def set_default_model(self, model_name: str) -> bool:
        """设置默认模型

        Args:
            model_name: 模型名称

        Returns:
            是否设置成功
        """
        return self._get_config().set_current_llm_model(model_name)

    def available_models(self) -> list:
        """获取可用模型列表

        Returns:
            可用模型名称列表
        """
        return self._config.get_available_models()

    def get_client_with_asset_manager(self, asset_manager) -> BaseLLMClient:
        """获取支持 tool 的客户端实例

        Args:
            asset_manager: AssetManager 实例，用于 tool 执行

        Returns:
            配置了 asset_manager 的 LLM 客户端
        """
        client = self.get_client()
        client.set_asset_manager(asset_manager)
        return client

    def _get_config(self) -> AppConfig:
        """获取配置实例

        Returns:
            AppConfig 实例
        """
        if self._config is None:
            from ..utils.config import config
            self._config = config
        return self._config

    def reset(self) -> None:
        """重置管理器，清除所有客户端缓存（主要用于测试）"""
        self._clients.clear()
        self._logger.debug("Client cache cleared")
