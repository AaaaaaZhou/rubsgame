"""
记忆精炼引擎配置模块
定义记忆精炼引擎的配置结构，通过 AppConfig 统一获取
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import logging

from ...utils.config import AppConfig

_logger = logging.getLogger("rubsgame.memory.config")


@dataclass
class BalanceStrategyConfig:
    """平衡策略配置"""
    keep_recent_turns: int = 10
    keep_system: bool = True
    compress_middle: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BalanceStrategyConfig":
        if not data:
            return cls()
        return cls(
            keep_recent_turns=data.get("keep_recent_turns", 10),
            keep_system=data.get("keep_system", True),
            compress_middle=data.get("compress_middle", True),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "keep_recent_turns": self.keep_recent_turns,
            "keep_system": self.keep_system,
            "compress_middle": self.compress_middle,
        }


@dataclass
class MemoryConfig:
    """记忆精炼引擎配置"""
    refine_threshold_tokens: int = 4000
    refine_max_turns: int = 20
    extraction_interval: int = 10
    extractor_llm_model: str = "deepseek_reasoner"
    max_memories_per_extraction: int = 5
    memory_priority_threshold: int = 5
    max_session_memories: int = 20
    max_world_memories: int = 50
    balance_strategy: BalanceStrategyConfig = field(default_factory=BalanceStrategyConfig)

    @classmethod
    def from_app_config(cls, config: Optional[AppConfig] = None) -> "MemoryConfig":
        """从 AppConfig 单例获取记忆配置（统一入口）"""
        if config is None:
            config = AppConfig.get_instance()

        mem_cfg = config.get_memory_config()

        strategy_data = mem_cfg.get("balance_strategy", {})
        if isinstance(strategy_data, dict):
            strategy = BalanceStrategyConfig.from_dict(strategy_data)
        else:
            strategy = BalanceStrategyConfig()

        return cls(
            refine_threshold_tokens=mem_cfg.get("refine_threshold_tokens", 4000),
            refine_max_turns=mem_cfg.get("refine_max_turns", 20),
            extraction_interval=mem_cfg.get("extraction_interval", 10),
            extractor_llm_model=mem_cfg.get("extractor_llm_model", "deepseek_reasoner"),
            max_memories_per_extraction=mem_cfg.get("max_memories_per_extraction", 5),
            memory_priority_threshold=mem_cfg.get("memory_priority_threshold", 5),
            max_session_memories=mem_cfg.get("max_session_memories", 20),
            max_world_memories=mem_cfg.get("max_world_memories", 50),
            balance_strategy=strategy,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "refine_threshold_tokens": self.refine_threshold_tokens,
            "refine_max_turns": self.refine_max_turns,
            "extraction_interval": self.extraction_interval,
            "extractor_llm_model": self.extractor_llm_model,
            "max_memories_per_extraction": self.max_memories_per_extraction,
            "memory_priority_threshold": self.memory_priority_threshold,
            "max_session_memories": self.max_session_memories,
            "max_world_memories": self.max_world_memories,
            "balance_strategy": self.balance_strategy.to_dict(),
        }