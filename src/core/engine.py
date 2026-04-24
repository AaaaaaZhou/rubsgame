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

    WORLD_TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "search_world",
                "description": "当你想了解清溪镇的地点、活动或知识时调用，例如：哪里可以骑车？哪里适合看日落？夏天去哪玩？",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keyword": {
                            "type": "string",
                            "description": "搜索关键词，可以是地点名称、活动类型、季节特征等"
                        }
                    },
                    "required": ["keyword"]
                }
            }
        }
    ]

    def __init__(self, config: Optional[AppConfig] = None, dev_mode: bool = False):
        self._config = config or AppConfig.get_instance()
        self._dev_mode = dev_mode
        self._session_mgr = SessionManager(self._config.session_dir)
        self._asset_mgr = AssetManager.get_instance()
        self._orchestrator = PromptOrchestrator(
            self._asset_mgr,
            model_name=self._config.current_llm_model
        )
        self._client_mgr = ClientManager.get_instance()
        self._memory_mgr = None
        _logger.info("EngineCore initialized")

    def _get_memory_manager(self):
        """懒加载记忆管理器"""
        if self._memory_mgr is None:
            from .memory import MemoryManager, MemoryConfig
            config = MemoryConfig.from_app_config(self._config)
            self._memory_mgr = MemoryManager(
                config=config,
                asset_manager=self._asset_mgr,
                client_manager=self._client_mgr
            )
        return self._memory_mgr

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

        # 2. 调用 LLM（支持 tool calling）
        client = self._client_mgr.get_client_with_asset_manager(self._asset_mgr)
        response_text = client.chat_with_tools(messages, tools=self.WORLD_TOOLS)

        # 3. 解析结构化输出
        parsed = self._parse_response(response_text)

        # 4. 记录历史（非 dev mode）
        if not self._dev_mode:
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
            npc_id = ""
            if self._asset_mgr.get_current_npc():
                npc_id = self._asset_mgr.get_current_npc().persona.name
            session = self._session_mgr.create_session(session_id, npc_id)
        return session

    def save_session(self, session_id: str) -> None:
        """保存会话"""
        session = self._session_mgr.get_session(session_id)
        if session:
            self._session_mgr.save_session(session)

    def finalize_and_save(self, session_id: str) -> None:
        """结束会话并保存（退出前调用）"""
        if self._dev_mode:
            return
        session = self._session_mgr.get_session(session_id)
        if session:
            # Phase 5: 调用记忆精炼引擎
            memory_mgr = self._get_memory_manager()
            memory_mgr.refine_and_extract(session, force=True)
            memory_mgr.trigger_extraction(session)
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

    def load_persona(self, npc_name: str):
        """加载 NPC 档案（persona + relationships + memories）"""
        return self._asset_mgr.load_npc(npc_name)

    def load_world(self, world_name: str):
        return self._asset_mgr.load_world(world_name)

    def list_sessions(self):
        return self._session_mgr.list_sessions()
