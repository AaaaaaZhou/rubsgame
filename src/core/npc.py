"""
NPC 数据模型模块
定义 NPCRelationship、NPCMemory、NPCProfile
"""
import time
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class NPCRelationship:
    """NPC 关系数据类"""
    subject_id: str           # 关系主体（如 NPC 名字）
    object_id: str            # 关系对象（如 "player" 或另一个 NPC）
    relation_type: str        # 关系类型: stranger/friend/rival/etc.
    affinity: int = 0         # 好感度 -100~100
    trust: int = 50          # 信任度 0~100
    key_events: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.affinity = max(-100, min(100, self.affinity))
        self.trust = max(0, min(100, self.trust))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "object_id": self.object_id,
            "relation_type": self.relation_type,
            "affinity": self.affinity,
            "trust": self.trust,
            "key_events": self.key_events,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NPCRelationship":
        return cls(
            subject_id=data.get("subject_id", ""),
            object_id=data.get("object_id", ""),
            relation_type=data.get("relation_type", "stranger"),
            affinity=data.get("affinity", 0),
            trust=data.get("trust", 50),
            key_events=data.get("key_events", []),
        )


@dataclass
class NPCMemory:
    """NPC 私人记忆数据类"""
    memory_id: str
    owner_id: str             # 所属 NPC
    content: str
    memory_type: str = "interaction"  # interaction/secret/observation
    importance: int = 5        # 0~10
    emotional_valence: int = 0  # -5~5
    linked_to: Optional[str] = None  # 关联对象
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self):
        self.importance = max(0, min(10, self.importance))
        self.emotional_valence = max(-5, min(5, self.emotional_valence))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "owner_id": self.owner_id,
            "content": self.content,
            "memory_type": self.memory_type,
            "importance": self.importance,
            "emotional_valence": self.emotional_valence,
            "linked_to": self.linked_to,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NPCMemory":
        return cls(
            memory_id=data.get("memory_id", ""),
            owner_id=data.get("owner_id", ""),
            content=data.get("content", ""),
            memory_type=data.get("memory_type", "interaction"),
            importance=data.get("importance", 5),
            emotional_valence=data.get("emotional_valence", 0),
            linked_to=data.get("linked_to"),
            timestamp=data.get("timestamp", time.time()),
        )


@dataclass
class NPCProfile:
    """NPC 完整档案：Persona + 关系网 + 私人记忆"""
    persona: Any              # Persona 对象（运行时类型）
    relationships: Dict[str, NPCRelationship] = field(default_factory=dict)  # key=object_id
    private_memories: List[NPCMemory] = field(default_factory=list)
    _logger: logging.Logger = field(default=None, repr=False)

    def __post_init__(self):
        if self._logger is None:
            self._logger = logging.getLogger(f"npc.profile")

    def get_relationship(self, object_id: str) -> Optional[NPCRelationship]:
        return self.relationships.get(object_id)

    def get_memory_context(self) -> str:
        if not self.private_memories:
            return "No private memories."
        lines = []
        for m in sorted(self.private_memories, key=lambda x: x.importance, reverse=True):
            lines.append(f"- [{m.memory_type}] {m.content}")
        return "\n".join(lines)

    def get_relationship_context(self) -> str:
        if not self.relationships:
            return "No relationship data."
        lines = []
        for obj_id, rel in self.relationships.items():
            lines.append(
                f"- {rel.object_id}: {rel.relation_type}, affinity={rel.affinity}, trust={rel.trust}"
            )
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relationships": {k: v.to_dict() for k, v in self.relationships.items()},
            "private_memories": [m.to_dict() for m in self.private_memories],
        }
