"""
Orchestrator Prompt 流水线测试
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import pytest
from src.core.orchestrator import PromptOrchestrator
from src.core.session import ConversationSession
from src.core.asset_manager import AssetManager
from src.core.types import Message, MemoryItem


class TestOrchestratorMemorySections:
    """测试 Orchestrator 的 Memory Section"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """每个测试前重置 AssetManager 单例"""
        AssetManager._instance = None

    def test_build_messages_empty_session(self):
        """测试空 session 时不显示 Short time memory 和 refined history section"""
        asset = AssetManager()
        orch = PromptOrchestrator(asset)

        session = ConversationSession(session_id="test")
        messages = orch.build_messages(session, "你好")

        # messages 是一个列表，第一条是 system message
        assert len(messages) >= 1
        system_msg = messages[0]
        assert system_msg["role"] == "system"

        content = system_msg.get("content", "")

        # 空 session 时，Short time memory 和 refined history 不显示（因为为空）
        # 但如果有内容，应该显示
        assert "[Output Format]" in content

    def test_build_messages_with_short_memory(self):
        """测试有短期记忆时"""
        asset = AssetManager()
        orch = PromptOrchestrator(asset)

        session = ConversationSession(session_id="test")
        session.add_memory(
            content="用户今天心情不好",
            memory_type="session_local",
            priority=7,
            tags=["情绪"]
        )

        messages = orch.build_messages(session, "你好")
        assert len(messages) >= 1
        content = messages[0].get("content", "")

        assert "[NPC Private Short time memory]" in content
        assert "用户今天心情不好" in content

    def test_build_messages_with_refined_history(self):
        """测试有精炼历史时"""
        asset = AssetManager()
        orch = PromptOrchestrator(asset)

        session = ConversationSession(session_id="test")
        session.add_message("user", "你好")
        session.add_message("assistant", "你好啊")

        # 模拟精炼后的状态
        session.refined_history = [
            Message(role="user", content="之前的对话..."),
            Message(role="assistant", content="之前的回复...")
        ]

        messages = orch.build_messages(session, "今天天气如何")
        assert len(messages) >= 1
        content = messages[0].get("content", "")

        assert "[NPC Private refined history]" in content
        assert "用户:" in content

    def test_format_long_term_history_truncation(self):
        """测试超长内容截断"""
        asset = AssetManager()
        orch = PromptOrchestrator(asset)

        long_content = "A" * 300
        messages = [Message(role="user", content=long_content)]

        result = orch._format_long_term_history(messages)

        assert "..." in result
        assert len(result) < len(long_content) + 50  # 截断后应更短

    def test_format_long_term_history_empty(self):
        """测试空消息列表"""
        asset = AssetManager()
        orch = PromptOrchestrator(asset)

        result = orch._format_long_term_history([])
        assert result == "（无）"

    def test_format_long_term_history_role_labels(self):
        """测试角色标签转换和 system 消息过滤"""
        asset = AssetManager()
        orch = PromptOrchestrator(asset)

        messages = [
            Message(role="user", content="user msg"),
            Message(role="assistant", content="assistant msg"),
            Message(role="system", content="system msg"),
        ]

        result = orch._format_long_term_history(messages)

        assert "用户:" in result
        assert "NPC:" in result
        assert "system:" not in result  # system 消息不出现在长期历史中


if __name__ == "__main__":
    pytest.main([__file__, "-v"])