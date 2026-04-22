"""
记忆管理器
统一调度记忆精炼和提取流程
"""
from typing import Dict, Any, List, Optional
import logging

from ..session import ConversationSession
from ..asset_manager import AssetManager
from src.clients.manager import ClientManager
from .config import MemoryConfig
from .refiner import BaseHistoryRefiner, BalancedHistoryRefiner
from .extractor import BaseMemoryExtractor, LLMMemoryExtractor
from ..types import MemoryItem

_logger = logging.getLogger("rubsgame.memory.manager")


class MemoryManager:
    """
    记忆管理器 - 协调精炼和提取流程

    主要职责:
    1. 触发条件检查（Token 限制、轮次限制）
    2. 调用 HistoryRefiner 精炼历史
    3. 调用 MemoryExtractor 提取记忆
    4. 更新 session.session_memories
    5. 更新 AssetManager 的全局记忆
    """

    def __init__(
        self,
        config: Optional[MemoryConfig] = None,
        asset_manager: Optional[AssetManager] = None,
        client_manager: Optional[ClientManager] = None
    ):
        self._config = config or MemoryConfig.from_app_config()
        self._asset_mgr = asset_manager or AssetManager.get_instance()
        self._client_mgr = client_manager or ClientManager.get_instance()

        self._refiner: BaseHistoryRefiner = BalancedHistoryRefiner()
        self._extractor: BaseMemoryExtractor = LLMMemoryExtractor(
            extraction_model=self._config.extractor_llm_model
        )

        self._last_extraction_turn: Dict[str, int] = {}

    def refine_and_extract(
        self,
        session: ConversationSession,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        执行记忆精炼和提取

        Args:
            session: 会话对象
            force: 是否强制执行（忽略阈值检查）

        Returns:
            执行结果字典 {
                "refined": bool,
                "extracted_count": int,
                "tokens_before": int,
                "tokens_after": int,
                "turn_count": int
            }
        """
        result = {
            "refined": False,
            "extracted_count": 0,
            "tokens_before": 0,
            "tokens_after": 0,
            "turn_count": sum(1 for m in session.full_history if m.role != "system")
        }

        if not force and not self._should_trigger(session):
            _logger.debug(
                f"MemoryManager: skipping - threshold not reached, "
                f"session={session.session_id}"
            )
            return result

        result["tokens_before"] = session.estimate_tokens()

        # 尝试 LLM 摘要（增强版）
        llm_summary = self._generate_llm_summary(session)

        # 精炼历史
        if llm_summary and hasattr(self._refiner, "refine_with_summary"):
            self._refiner.refine_with_summary(session, self._config, llm_summary)
        else:
            self._refiner.refine(session, self._config)

        result["refined"] = True
        result["tokens_after"] = session.estimate_tokens()

        # 提取记忆
        current_turns = len(session.full_history)
        last_extraction = self._last_extraction_turn.get(session.session_id, 0)

        if current_turns - last_extraction >= self._config.extraction_interval:
            memories = self._extract_memories(session)
            result["extracted_count"] = len(memories)
            self._last_extraction_turn[session.session_id] = current_turns

        _logger.info(
            f"MemoryManager: completed for session={session.session_id}, "
            f"refined={result['refined']}, extracted={result['extracted_count']}"
        )

        return result

    def _should_trigger(self, session: ConversationSession) -> bool:
        tokens = session.estimate_tokens()
        if tokens >= self._config.refine_threshold_tokens:
            _logger.debug(f"Token threshold reached: {tokens} >= {self._config.refine_threshold_tokens}")
            return True

        turns = sum(1 for m in session.full_history if m.role != "system")
        if turns >= self._config.refine_max_turns:
            _logger.debug(f"Turn threshold reached: {turns} >= {self._config.refine_max_turns}")
            return True

        return False

    def _generate_llm_summary(self, session: ConversationSession) -> Optional[str]:
        """生成 LLM 摘要（可选增强功能）"""
        dialog_msgs = [m for m in session.full_history if m.role != "system"]
        middle_count = max(0, len(dialog_msgs) - self._config.balance_strategy.keep_recent_turns * 2)

        if middle_count < 10:
            return None

        try:
            client = self._client_mgr.get_client(self._config.extractor_llm_model)
            middle_msgs = dialog_msgs[:-self._config.balance_strategy.keep_recent_turns * 2]
            history_text = "\n".join(
                f"{m.role}: {m.content[:200]}..." if len(m.content) > 200 else f"{m.role}: {m.content}"
                for m in middle_msgs[-20:]
            )

            summary_prompt = f"""请简要概括以下对话的核心内容（100字以内）：

{history_text}

摘要："""

            summary = client.chat([{"role": "user", "content": summary_prompt}])
            return summary.strip() if summary else None

        except Exception as e:
            _logger.warning(f"LLM summary generation failed: {e}")
            return None

    def _extract_memories(self, session: ConversationSession) -> List[MemoryItem]:
        """提取并存储记忆"""
        try:
            client = self._client_mgr.get_client(self._config.extractor_llm_model)
            memories = self._extractor.extract(session, llm_client=client, config=self._config)

            session_local_memories = []
            world_global_memories = []

            for memory in memories:
                if memory.memory_type == "world_global":
                    world_global_memories.append(memory)
                else:
                    session_local_memories.append(memory)

            session.session_memories.extend(session_local_memories)

            if len(session.session_memories) > self._config.max_session_memories:
                session.session_memories.sort(key=lambda m: m.priority, reverse=True)
                session.session_memories = session.session_memories[:self._config.max_session_memories]

            for memory in world_global_memories:
                self._asset_mgr.update_global_memory(memory)

            _logger.info(
                f"MemoryManager: extracted {len(memories)} memories, "
                f"session_local={len(session_local_memories)}, "
                f"world_global={len(world_global_memories)}"
            )

            return memories

        except Exception as e:
            _logger.error(f"Memory extraction failed: {e}")
            return []

    def trigger_extraction(self, session: ConversationSession) -> List[MemoryItem]:
        """手动触发记忆提取（会话退出时用，不执行精炼）"""
        return self._extract_memories(session)

    @property
    def config(self) -> MemoryConfig:
        return self._config

    def update_config(self, config: MemoryConfig) -> None:
        self._config = config