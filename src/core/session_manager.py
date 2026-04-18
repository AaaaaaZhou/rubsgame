"""
会话管理器模块
负责会话的创建、保存、加载和 Token 管理
"""
import json
import os
import logging
from typing import Dict, List, Optional

from .session import ConversationSession
from .types import Message
from ..utils.logger import get_logger

_logger = get_logger("rubsgame.session")


class SessionManager:
    """会话管理器"""

    def __init__(self, session_dir: str = "data/sessions/"):
        self._session_dir = session_dir
        self._sessions: Dict[str, ConversationSession] = {}
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        os.makedirs(self._session_dir, exist_ok=True)

    def _get_file_path(self, session_id: str) -> str:
        return os.path.join(self._session_dir, f"{session_id}.json")

    def create_session(
        self,
        session_id: str,
        bound_persona_file: str = ""
    ) -> ConversationSession:
        """创建新会话"""
        if session_id in self._sessions:
            _logger.warning(f"Session {session_id} already exists, returning existing")
            return self._sessions[session_id]

        session = ConversationSession(session_id, bound_persona_file)
        self._sessions[session_id] = session
        _logger.info(f"Created session: {session_id}")
        return session

    def save_session(self, session: ConversationSession) -> None:
        """保存会话到磁盘"""
        file_path = self._get_file_path(session.session_id)
        data = session.to_dict()
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        _logger.debug(f"Saved session {session.session_id} to {file_path}")

    def load_session(self, session_id: str) -> ConversationSession:
        """从磁盘加载会话"""
        if session_id in self._sessions:
            return self._sessions[session_id]

        file_path = self._get_file_path(session_id)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Session file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        session = ConversationSession.from_dict(data)
        self._sessions[session_id] = session
        _logger.info(f"Loaded session: {session_id}")
        return session

    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """获取会话（不创建）"""
        return self._sessions.get(session_id)

    def append_message(
        self,
        session: ConversationSession,
        role: str,
        content: str
    ) -> Message:
        """添加消息到会话"""
        return session.add_message(role, content)

    def trim_history(
        self,
        session: ConversationSession,
        max_turns: int = 20
    ) -> None:
        """滑动窗口裁剪历史"""
        if len(session.refined_history) <= max_turns:
            return

        # 保留系统消息头尾 + 最近 N 轮
        system_msgs = [m for m in session.refined_history if m.role == "system"]
        dialog_msgs = [m for m in session.refined_history if m.role != "system"]

        keep = max_turns // 2
        trimmed = system_msgs + dialog_msgs[:keep] + dialog_msgs[-keep:]
        session.refined_history = trimmed
        _logger.debug(f"Trimmed history for {session.session_id}, kept {len(trimmed)} msgs")

    def estimate_tokens(self, session: ConversationSession) -> int:
        """估算 Token 使用量"""
        return session.estimate_tokens()

    def list_sessions(self) -> List[str]:
        """列出所有会话 ID"""
        return list(self._sessions.keys())

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]

        file_path = self._get_file_path(session_id)
        if os.path.exists(file_path):
            os.remove(file_path)
            _logger.info(f"Deleted session: {session_id}")
            return True
        return False
