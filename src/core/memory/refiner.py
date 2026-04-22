"""
历史精炼模块
提供多种历史压缩策略
"""
from abc import ABC, abstractmethod
from typing import List, Optional
import logging

from ..session import ConversationSession
from ..types import Message
from .config import MemoryConfig

_logger = logging.getLogger("rubsgame.memory.refiner")


class BaseHistoryRefiner(ABC):
    """历史精炼器抽象基类"""

    @abstractmethod
    def refine(
        self,
        session: ConversationSession,
        config: MemoryConfig
    ) -> None:
        """
        执行历史精炼

        Args:
            session: 会话对象
            config: 记忆配置

        Note:
            此方法直接修改 session.refined_history
        """
        pass

    def _estimate_turns(self, session: ConversationSession) -> int:
        """估算对话轮次（排除系统消息）"""
        return sum(1 for msg in session.full_history if msg.role != "system")

    def _estimate_token_count(self, session: ConversationSession) -> int:
        """估算当前 refined_history 的 token 数"""
        total = 0
        for msg in session.refined_history:
            total += len(msg.content) // 4
        return total


class BalancedHistoryRefiner(BaseHistoryRefiner):
    """
    平衡策略精炼器

    策略说明:
    1. 保留最近的 N 轮对话（user + assistant 配对）
    2. 保留首部系统消息（系统设定等）
    3. 中间部分压缩为摘要占位符
    """

    def __init__(self, summary_placeholder: str = "[此处为之前对话的摘要]"):
        """
        Args:
            summary_placeholder: 摘要占位符文本
        """
        self._summary_placeholder = summary_placeholder

    def refine(
        self,
        session: ConversationSession,
        config: MemoryConfig
    ) -> None:
        """执行平衡策略精炼（占位符摘要）"""
        strategy = config.balance_strategy
        full_history = session.full_history

        if not full_history:
            return

        # 分离系统消息和对话消息
        system_msgs = [m for m in full_history if m.role == "system"]
        dialog_msgs = [m for m in full_history if m.role != "system"]

        keep_recent = strategy.keep_recent_turns
        total_turns = len(dialog_msgs) // 2  # 每轮包含 user + assistant

        # 构建精炼历史
        refined: List[Message] = []

        # 保留系统头
        if strategy.keep_system and system_msgs:
            refined.append(system_msgs[0])

        # 中间部分压缩
        if total_turns > keep_recent * 2:
            if strategy.compress_middle:
                summary_msg = Message(
                    role="system",
                    content=self._generate_middle_summary(
                        total_turns - keep_recent,
                        keep_recent
                    ),
                    metadata={"is_summary": True}
                )
                refined.append(summary_msg)
            else:
                # 直接裁剪，只保留首尾
                middle_end = len(dialog_msgs) - keep_recent
                refined.extend(dialog_msgs[:middle_end])

        # 最近的 N 轮对话
        refined.extend(dialog_msgs[-keep_recent * 2:] if keep_recent > 0 else [])

        # 更新会话
        session.refined_history = refined
        _logger.info(
            f"BalancedHistoryRefiner: refined {len(full_history)} -> {len(refined)} msgs, "
            f"total_turns={total_turns}, keep_recent={keep_recent}"
        )

    def _generate_middle_summary(
        self,
        compressed_turns: int,
        keep_recent: int
    ) -> str:
        """生成中间部分的摘要文本（占位符）"""
        return (
            f"[对话摘要] 之前的 {compressed_turns} 轮对话已压缩。\n"
            f"{self._summary_placeholder}\n"
            f"（最近 {keep_recent} 轮对话保留在下方）"
        )

    def refine_with_summary(
        self,
        session: ConversationSession,
        config: MemoryConfig,
        llm_summary: str
    ) -> None:
        """
        使用 LLM 生成的真实摘要进行精炼

        Args:
            session: 会话对象
            config: 记忆配置
            llm_summary: LLM 生成的摘要文本
        """
        strategy = config.balance_strategy
        full_history = session.full_history

        if not full_history:
            return

        # 分离消息
        system_msgs = [m for m in full_history if m.role == "system"]
        dialog_msgs = [m for m in full_history if m.role != "system"]

        # 构建精炼历史
        refined: List[Message] = []

        # 保留系统头
        if strategy.keep_system and system_msgs:
            refined.append(system_msgs[0])

        # 使用 LLM 真实摘要
        summary_msg = Message(
            role="system",
            content=f"[对话摘要]\n{llm_summary}",
            metadata={"is_summary": True, "is_llm_summary": True}
        )
        refined.append(summary_msg)

        # 保留最近的对话
        keep_recent = strategy.keep_recent_turns
        refined.extend(dialog_msgs[-keep_recent * 2:] if keep_recent > 0 else [])

        # 尾部系统消息
        if strategy.keep_system and len(system_msgs) > 1:
            refined.append(system_msgs[-1])

        session.refined_history = refined
        _logger.info(
            f"BalancedHistoryRefiner: refined with LLM summary, "
            f"{len(full_history)} -> {len(refined)} msgs"
        )