"""
Prompt 编排器模块
按固定顺序组装 Prompt：World → Persona → Memory → History → Input → Constraint
"""
import logging
from typing import Dict, List, Optional

from .asset_manager import AssetManager
from .session import ConversationSession
from .types import Message
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

    def __init__(self, asset_manager: AssetManager):
        self._asset = asset_manager

    def build_messages(
        self,
        session: ConversationSession,
        user_input: str,
        include_memory: bool = True
    ) -> List[Dict[str, str]]:
        """组装消息列表

        顺序:
        1. System: World Context
        2. System: Persona Context
        3. System: Memory Context (if include_memory)
        4. History: refined_history
        5. User: user_input
        6. System: Output Constraint
        """
        messages: List[Dict[str, str]] = []

        # 1. World Context
        world_ctx = self._asset.get_world_context()
        if world_ctx:
            messages.append({
                "role": "system",
                "content": f"[World]\n{world_ctx}"
            })

        # 2. Persona Context
        persona_prompt = self._asset.get_persona_system_prompt()
        if persona_prompt:
            messages.append({
                "role": "system",
                "content": f"[Character]\n{persona_prompt}"
            })

        # 3. Memory Context
        if include_memory and session.session_memories:
            mem_ctx = self._build_memory_context(session.session_memories)
            messages.append({
                "role": "system",
                "content": f"[Memory]\n{mem_ctx}"
            })

        # 4. History
        for msg in session.refined_history:
            messages.append({
                "role": msg.role,
                "content": msg.content
            })

        # 5. User Input
        messages.append({
            "role": "user",
            "content": user_input
        })

        # 6. Output Constraint
        messages.append({
            "role": "system",
            "content": f"[Output Format]\nYou must respond in valid JSON:\n{self._format_schema()}"
        })

        _logger.debug(f"Built {len(messages)} messages for session {session.session_id}")
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
