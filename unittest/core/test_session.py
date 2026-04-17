"""
会话数据模型测试
"""
import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import pytest
from core.session import Message, MemoryItem, ConversationSession


class TestMessage:
    """测试Message类"""
    
    def test_message_creation(self):
        """测试消息创建"""
        msg = Message(role="user", content="Hello, world!")
        assert msg.role == "user"
        assert msg.content == "Hello, world!"
        assert isinstance(msg.timestamp, float)
        assert msg.metadata == {}
    
    def test_message_to_dict(self):
        """测试消息序列化"""
        msg = Message(role="assistant", content="Hi there", metadata={"emotion": "happy"})
        data = msg.to_dict()
        
        assert data["role"] == "assistant"
        assert data["content"] == "Hi there"
        assert data["metadata"]["emotion"] == "happy"
        assert "timestamp" in data
    
    def test_message_from_dict(self):
        """测试消息反序列化"""
        original = Message(role="system", content="System message")
        data = original.to_dict()
        
        restored = Message.from_dict(data)
        assert restored.role == original.role
        assert restored.content == original.content
        assert abs(restored.timestamp - original.timestamp) < 0.001
    
    def test_message_formatted_time(self):
        """测试格式化时间"""
        msg = Message(role="user", content="test")
        time_str = msg.formatted_time
        assert isinstance(time_str, str)
        assert ":" in time_str  # 简单检查格式


class TestMemoryItem:
    """测试MemoryItem类"""
    
    def test_memory_item_creation(self):
        """测试记忆项创建"""
        memory = MemoryItem(
            content="用户喜欢咖啡",
            memory_type="session_local",
            priority=7,
            tags=["preference", "food"]
        )
        
        assert memory.content == "用户喜欢咖啡"
        assert memory.memory_type == "session_local"
        assert memory.priority == 7
        assert memory.tags == ["preference", "food"]
        assert isinstance(memory.created_at, float)
    
    def test_memory_item_validation(self):
        """测试记忆项验证"""
        # 测试无效优先级
        with pytest.raises(ValueError):
            MemoryItem(content="test", memory_type="session_local", priority=11)
        
        with pytest.raises(ValueError):
            MemoryItem(content="test", memory_type="session_local", priority=-1)
        
        # 测试空内容
        with pytest.raises(ValueError):
            MemoryItem(content="   ", memory_type="session_local")
    
    def test_memory_item_to_dict(self):
        """测试记忆项序列化"""
        memory = MemoryItem(
            content="重要信息",
            memory_type="world_global",
            priority=9,
            tags=["important"]
        )
        
        data = memory.to_dict()
        assert data["content"] == "重要信息"
        assert data["memory_type"] == "world_global"
        assert data["priority"] == 9
        assert data["tags"] == ["important"]
        assert "created_at" in data
    
    def test_memory_item_from_dict(self):
        """测试记忆项反序列化"""
        original = MemoryItem(
            content="测试记忆",
            memory_type="session_local",
            priority=5,
            tags=["test"]
        )
        
        data = original.to_dict()
        restored = MemoryItem.from_dict(data)
        
        assert restored.content == original.content
        assert restored.memory_type == original.memory_type
        assert restored.priority == original.priority
        assert restored.tags == original.tags
        assert abs(restored.created_at - original.created_at) < 0.001
    
    def test_memory_item_add_tag(self):
        """测试添加标签"""
        memory = MemoryItem(content="test", memory_type="session_local")
        
        memory.add_tag("tag1")
        assert "tag1" in memory.tags
        
        # 测试去重
        memory.add_tag("tag1")
        assert memory.tags.count("tag1") == 1
        
        memory.add_tag("tag2")
        assert set(memory.tags) == {"tag1", "tag2"}


class TestConversationSession:
    """测试ConversationSession类"""
    
    def test_session_creation(self):
        """测试会话创建"""
        session = ConversationSession(session_id="test-123")
        
        assert session.session_id == "test-123"
        assert session.bound_persona_file == ""
        assert session.full_history == []
        assert session.refined_history == []
        assert session.session_memories == []
    
    def test_add_message(self):
        """测试添加消息"""
        session = ConversationSession(session_id="test-123")
        
        msg = session.add_message("user", "Hello!")
        assert isinstance(msg, Message)
        assert msg.role == "user"
        assert msg.content == "Hello!"
        
        assert len(session.full_history) == 1
        assert len(session.refined_history) == 1
        assert session.full_history[0] == msg
        assert session.refined_history[0] == msg
    
    def test_add_message_invalid_role(self):
        """测试添加无效角色的消息"""
        session = ConversationSession(session_id="test-123")
        
        with pytest.raises(ValueError):
            session.add_message("invalid_role", "message")
    
    def test_add_memory(self):
        """测试添加记忆"""
        session = ConversationSession(session_id="test-123")
        
        memory = session.add_memory(
            content="用户偏好",
            memory_type="session_local",
            priority=8,
            tags=["preference"]
        )
        
        assert isinstance(memory, MemoryItem)
        assert memory.content == "用户偏好"
        assert memory.memory_type == "session_local"
        assert memory.priority == 8
        assert memory.tags == ["preference"]
        
        assert len(session.session_memories) == 1
        assert session.session_memories[0] == memory
    
    def test_session_to_dict(self):
        """测试会话序列化"""
        session = ConversationSession(session_id="test-123", bound_persona_file="alice.yaml")
        
        session.add_message("user", "Hi")
        session.add_message("assistant", "Hello!")
        session.add_memory("测试记忆", "session_local")
        
        data = session.to_dict()
        
        assert data["session_id"] == "test-123"
        assert data["bound_persona_file"] == "alice.yaml"
        assert len(data["full_history"]) == 2
        assert len(data["refined_history"]) == 2
        assert len(data["session_memories"]) == 1
    
    def test_session_from_dict(self):
        """测试会话反序列化"""
        # 创建原始会话
        original = ConversationSession(session_id="test-456", bound_persona_file="bob.yaml")
        original.add_message("user", "Message 1")
        original.add_message("assistant", "Response 1")
        original.add_memory("记忆内容", "world_global", priority=9)
        
        # 序列化和反序列化
        data = original.to_dict()
        restored = ConversationSession.from_dict(data)
        
        assert restored.session_id == original.session_id
        assert restored.bound_persona_file == original.bound_persona_file
        assert len(restored.full_history) == len(original.full_history)
        assert len(restored.refined_history) == len(original.refined_history)
        assert len(restored.session_memories) == len(original.session_memories)
        
        # 验证消息内容
        for orig_msg, restored_msg in zip(original.full_history, restored.full_history):
            assert orig_msg.role == restored_msg.role
            assert orig_msg.content == restored_msg.content
    
    def test_estimate_tokens(self):
        """测试Token估算"""
        session = ConversationSession(session_id="test-123")
        
        # 空会话
        assert session.estimate_tokens() == 0
        
        # 添加一些消息
        session.add_message("user", "Hello world")  # 11字符
        session.add_message("assistant", "Hi there!")  # 10字符
        
        # 估算：21字符 / 4 ≈ 5个token
        tokens = session.estimate_tokens()
        assert tokens == 5  # 21 // 4 = 5
    
    def test_get_recent_messages(self):
        """测试获取最近消息"""
        session = ConversationSession(session_id="test-123")
        
        # 添加5条消息
        for i in range(5):
            session.add_message("user", f"Message {i}")
        
        recent = session.get_recent_messages(3)
        assert len(recent) == 3
        assert recent[0].content == "Message 2"
        assert recent[2].content == "Message 4"
    
    def test_clear_refined_history(self):
        """测试清空精炼历史"""
        session = ConversationSession(session_id="test-123")
        
        session.add_message("user", "Message")
        assert len(session.refined_history) == 1
        
        session.clear_refined_history()
        assert len(session.refined_history) == 0
        assert len(session.full_history) == 1  # 完整历史不受影响
    
    def test_session_str_repr(self):
        """测试字符串表示"""
        session = ConversationSession(session_id="test-123")
        
        session.add_message("user", "Hello")
        session.add_memory("记忆", "session_local")
        
        str_repr = str(session)
        assert "test-123" in str_repr
        assert "messages=1" in str_repr
        assert "memories=1" in str_repr
        
        repr_repr = repr(session)
        assert "ConversationSession" in repr_repr
        assert "test-123" in repr_repr


if __name__ == "__main__":
    pytest.main([__file__, "-v"])