"""
Prompt 编排器模块
按固定顺序组装 Prompt：World → Persona → Memory → History → Input → Constraint
支持多模型消息格式，通过 schema 差异化处理
"""
import logging
from typing import Any, Dict, List, Optional

from .asset_manager import AssetManager
from .session import ConversationSession
from .types import Message
from .config import get_message_schema
from ..utils.logger import get_logger

_logger = get_logger("rubsgame.orchestrator")


class PromptOrchestrator:
    """Prompt 编排器 - 无状态，按依赖顺序组装"""

    OUTPUT_SCHEMA = {
        "type": "json_object",
        "properties": {
            "content": {"type": "string", "description": "对话回复内容"},
            "emotion": {"type": "string", "description": "情绪标签，如 happy/sad/angry/surprised/neutral"},
            "intensity": {"type": "number", "description": "情绪强度 0.0-1.0"}
        },
        "required": ["content", "emotion", "intensity"]
    }

    def __init__(self, asset_manager: AssetManager, model_name: Optional[str] = None):
        self._asset = asset_manager
        self._model_name = model_name
        self._schema = get_message_schema(model_name or "deepseek_reasoner")

    def build_messages(
        self,
        session: ConversationSession,
        user_input: str,
        include_memory: bool = True
    ) -> List[Dict[str, Any]]:
        """组装消息列表

        收集各模块内容后，委托给 schema 进行模型相关的格式化
        """
        # 1. World Context
        parts = []
        world_ctx = self._asset.get_world_context()
        if world_ctx:
            parts.append(f"[World]\n{world_ctx}")

        # 2. Persona Context
        persona_prompt = self._asset.get_persona_system_prompt()
        if persona_prompt:
            parts.append(f"[Character]\n{persona_prompt}")

        # 3. NPC Relationship Context
        rel_ctx = self._asset.get_npc_relationship_context()
        if rel_ctx:
            parts.append(f"[NPC Relationship]\n{rel_ctx}")

        # 4. NPC Private Memory Context
        mem_ctx = self._asset.get_npc_memory_context()
        if mem_ctx:
            parts.append(f"[NPC Private Memory]\n{mem_ctx}")

        # 5. Memory Context
        if include_memory and session.session_memories:
            session_mem = self._build_memory_context(session.session_memories)
            parts.append(f"[Memory]\n{session_mem}")

        # 6. Output Constraint
        parts.append(f"[Output Format]\nYou must respond in valid JSON:\n{self._format_schema()}")

        system_content = "\n\n".join(parts)

        # 构建 history 列表
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in session.refined_history
        ]

        # 委托给 schema 进行模型相关的格式化
        messages = self._schema.build_messages(
            system_content=system_content,
            history=history,
            user_input=user_input,
            npc_name=session.bound_npc_id
        )

        _logger.debug(f"Built {len(messages)} messages for session {session.session_id} using {self._model_name} schema")
        return messages

    def _build_memory_context(self, memories: List) -> str:
        lines = []
        for m in memories:
            tag_str = f"[{', '.join(m.tags)}]" if m.tags else ""
            lines.append(f"- {m.content} {tag_str}")
        return "\n".join(lines) if lines else "No memories yet."

    def _format_schema(self) -> str:
        import json
        return json.dumps(self.OUTPUT_SCHEMA, indent=2, ensure_ascii=False)
