"""
会话数据模型模块
定义对话消息、记忆项和会话状态的数据结构
"""
import time
import logging
from typing import Dict, List, Any, Optional

from .types import Message, MemoryItem


class ConversationSession:
    """对话会话 - 管理会话状态和历史"""
    
    def __init__(
        self,
        session_id: str,
        bound_persona_file: str = "",
        logger: Optional[logging.Logger] = None
    ):
        """初始化会话
        
        Args:
            session_id: 会话唯一标识符
            bound_persona_file: 绑定的人设文件名
            logger: 可选的日志记录器
        """
        self.session_id = session_id
        self.bound_npc_id = bound_persona_file  # 保持兼容：旧会话文件仍用此字段
        self.full_history: List[Message] = []        # 完整历史（永不删除）
        self.refined_history: List[Message] = []     # 精炼历史（用于Prompt）
        self.session_memories: List[MemoryItem] = [] # 会话专属记忆
        self._logger = logger or logging.getLogger(f"session.{session_id}")
        self._logger.info(f"Session {session_id} initialized")
    
    def add_message(self, role: str, content: str) -> Message:
        """添加消息到完整历史和精炼历史
        
        Args:
            role: 消息角色 (system/user/assistant)
            content: 消息内容
            
        Returns:
            创建的Message对象
        """
        if role not in ("system", "user", "assistant"):
            raise ValueError(f"Invalid role: {role}")
        
        message = Message(role=role, content=content)
        self.full_history.append(message)
        self.refined_history.append(message)  # 初始时两者相同，后续精炼会修改
        
        self._logger.debug(f"Added {role} message: {content[:50]}...")
        return message
    
    def add_memory(self, content: str, memory_type: str, priority: int = 5, tags: Optional[List[str]] = None) -> MemoryItem:
        """添加记忆项
        
        Args:
            content: 记忆内容
            memory_type: 记忆类型 (session_local/world_global)
            priority: 优先级 (0-10)
            tags: 标签列表
            
        Returns:
            创建的MemoryItem对象
        """
        memory = MemoryItem(
            content=content,
            memory_type=memory_type,
            priority=priority,
            tags=tags or []
        )
        self.session_memories.append(memory)
        self._logger.debug(f"Added {memory_type} memory: {content[:50]}...")
        return memory
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为可序列化的字典

        Returns:
            包含会话所有数据的字典
        """
        return {
            "session_id": self.session_id,
            "bound_npc_id": self.bound_npc_id,
            "full_history": [msg.to_dict() for msg in self.full_history],
            "refined_history": [msg.to_dict() for msg in self.refined_history],
            "session_memories": [mem.to_dict() for mem in self.session_memories],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationSession":
        """从字典还原会话

        Args:
            data: 会话数据字典

        Returns:
            恢复的ConversationSession对象
        """
        # 兼容旧字段名 bound_persona_file
        bound_npc = data.get("bound_npc_id", data.get("bound_persona_file", ""))
        session = cls(
            session_id=data["session_id"],
            bound_persona_file=bound_npc
        )
        
        # 恢复消息历史
        for msg_data in data.get("full_history", []):
            session.full_history.append(Message.from_dict(msg_data))
        
        for msg_data in data.get("refined_history", []):
            session.refined_history.append(Message.from_dict(msg_data))
        
        # 恢复记忆
        for mem_data in data.get("session_memories", []):
            session.session_memories.append(MemoryItem.from_dict(mem_data))
        
        session._logger.info(f"Session {session.session_id} restored from dict")
        return session
    
    def estimate_tokens(self) -> int:
        """估算当前会话的Token使用量（简单实现）
        
        Returns:
            估算的Token数量
        """
        total_chars = 0
        for msg in self.full_history:
            total_chars += len(msg.content)
        # 简单估算：4个字符约等于1个token
        return total_chars // 4
    
    def get_recent_messages(self, count: int = 10) -> List[Message]:
        """获取最近的消息
        
        Args:
            count: 消息数量
            
        Returns:
            最近的消息列表
        """
        return self.full_history[-count:] if self.full_history else []
    
    def clear_refined_history(self) -> None:
        """清空精炼历史（用于重新精炼）"""
        self.refined_history.clear()
        self._logger.debug("Refined history cleared")
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"ConversationSession(id={self.session_id}, messages={len(self.full_history)}, memories={len(self.session_memories)})"
    
    def __repr__(self) -> str:
        """详细表示"""
        return f"ConversationSession(session_id={self.session_id!r}, bound_npc_id={self.bound_npc_id!r})"