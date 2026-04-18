"""
对话引擎核心模块
整合 SessionManager、AssetManager、PromptOrchestrator、ClientManager
提供统一的 chat() 入口
"""
import json
import logging
from typing import Any, Dict, Optional

from .session import ConversationSession
from .session_manager import SessionManager
from .asset_manager import AssetManager
from .orchestrator import PromptOrchestrator
from .types import Message
from ..clients.manager import ClientManager
from ..utils.config import AppConfig
from ..utils.logger import get_logger

_logger = get_logger("rubsgame.engine")


class EngineCore:
    """对话引擎核心 - 门面类"""

    def __init__(self, config: Optional[AppConfig] = None):
        self._config = config or AppConfig.get_instance()
        self._session_mgr = SessionManager(self._config.session_dir)
        self._asset_mgr = AssetManager.get_instance()
        self._orchestrator = PromptOrchestrator(self._asset_mgr)
        self._client_mgr = ClientManager.get_instance()
        _logger.info("EngineCore initialized")

    def chat(
        self,
        user_input: str,
        session_id: str = "default"
    ) -> Dict[str, Any]:
        """对话接口

        Args:
            user_input: 用户输入
            session_id: 会话 ID

        Returns:
            {
                "content": str,
                "emotion": str,
                "intensity": float,
                "session_id": str
            }
        """
        session = self.get_or_create_session(session_id)

        # 1. 构建 Prompt
        messages = self._orchestrator.build_messages(session, user_input)

        # 2. 调用 LLM
        client = self._client_mgr.get_client()
        response_text = client.chat(messages)

        # 3. 解析结构化输出
        parsed = self._parse_response(response_text)

        # 4. 记录历史
        session.add_message("user", user_input)
        session.add_message("assistant", parsed["content"])

        _logger.debug(f"Chat completed for {session_id}: emotion={parsed['emotion']}")
        return {
            "content": parsed["content"],
            "emotion": parsed["emotion"],
            "intensity": parsed["intensity"],
            "session_id": session_id
        }

    def _parse_response(self, text: str) -> Dict[str, Any]:
        """解析 LLM 返回，尝试提取 JSON 结构化内容"""
        try:
            # 尝试从文本中提取 JSON
            json_str = self._extract_json(text)
            data = json.loads(json_str)
            return {
                "content": data.get("content", text),
                "emotion": data.get("emotion", "neutral"),
                "intensity": float(data.get("intensity", 0.5))
            }
        except Exception:
            # 回退：直接返回原文
            return {
                "content": text,
                "emotion": "neutral",
                "intensity": 0.5
            }

    def _extract_json(self, text: str) -> str:
        """从文本中提取 JSON 字符串"""
        import re
        # 尝试找 ```json ... ``` 块
        match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            return match.group(1)
        # 尝试找第一个 { ... }
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            return match.group(1)
        return text

    # ==================== Session Management ====================

    def get_or_create_session(self, session_id: str) -> ConversationSession:
        """获取或创建会话"""
        session = self._session_mgr.get_session(session_id)
        if session is None:
            persona_name = ""
            if self._asset_mgr.get_current_persona():
                persona_name = self._asset_mgr.get_current_persona().name
            session = self._session_mgr.create_session(session_id, persona_name)
        return session

    def save_session(self, session_id: str) -> None:
        """保存会话"""
        session = self._session_mgr.get_session(session_id)
        if session:
            self._session_mgr.save_session(session)

    def finalize_and_save(self, session_id: str) -> None:
        """结束会话并保存（退出前调用）"""
        session = self._session_mgr.get_session(session_id)
        if session:
            # TODO: Phase 5 调用记忆精炼引擎
            self._session_mgr.save_session(session)
            _logger.info(f"Session {session_id} finalized and saved")

    def get_status(self, session_id: str) -> Dict[str, Any]:
        """获取会话状态"""
        session = self._session_mgr.get_session(session_id)
        if session is None:
            return {"error": "Session not found"}

        persona = self._asset_mgr.get_current_persona()
        world = self._asset_mgr.get_current_world()

        return {
            "session_id": session_id,
            "persona": persona.name if persona else None,
            "world": world.world_name if world else None,
            "history_count": len(session.full_history),
            "memory_count": len(session.session_memories),
            "token_estimate": session.estimate_tokens()
        }

    # ==================== Delegate Methods ====================

    def load_persona(self, persona_name: str):
        return self._asset_mgr.load_persona(persona_name)

    def load_world(self, world_name: str):
        return self._asset_mgr.load_world(world_name)

    def list_sessions(self):
        return self._session_mgr.list_sessions()
