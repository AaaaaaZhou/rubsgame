"""
公共数据类型模块
定义跨模块共享的原子数据结构
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Any
from datetime import datetime


@dataclass
class Message:
    """对话消息"""
    role: Literal["system", "user", "assistant"]
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata", {})
        )

    @property
    def formatted_time(self) -> str:
        return datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S")


@dataclass
class MemoryItem:
    """记忆项 - 用于会话记忆和全局世界观记忆"""
    content: str
    memory_type: Literal["session_local", "world_global"]
    priority: int = field(default=5)
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not 0 <= self.priority <= 10:
            raise ValueError(f"Priority must be between 0 and 10, got {self.priority}")
        if not self.content.strip():
            raise ValueError("Memory content cannot be empty")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "memory_type": self.memory_type,
            "priority": self.priority,
            "tags": self.tags,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryItem":
        return cls(
            content=data["content"],
            memory_type=data["memory_type"],
            priority=data.get("priority", 5),
            tags=data.get("tags", []),
            created_at=data.get("created_at", time.time())
        )

    def add_tag(self, tag: str) -> None:
        if tag not in self.tags:
            self.tags.append(tag)
