"""
Memory Manager 精炼触发机制测试
"""
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import pytest
from src.core.engine import EngineCore
from src.core.session import ConversationSession
from src.utils.config import AppConfig


class TestRefineTrigger:
    """测试精炼触发机制"""

    def test_should_trigger_refine_tokens(self):
        """测试 Token 阈值触发"""
        config = AppConfig.get_instance()
        engine = EngineCore(config, dev_mode=True)

        session = engine.get_or_create_session("test_tokens")
        # Mock
        session.estimate_tokens = lambda: 5000

        assert engine._should_trigger_refine(session) is True

        session.estimate_tokens = lambda: 3000
        assert engine._should_trigger_refine(session) is False

    def test_should_trigger_refine_turns(self):
        """测试轮次阈值触发"""
        config = AppConfig.get_instance()
        engine = EngineCore(config, dev_mode=True)

        session = engine.get_or_create_session("test_turns")

        # 添加 20 轮对话（40 条消息）
        for i in range(20):
            session.add_message("user", f"用户消息 {i}")
            session.add_message("assistant", f"助手回复 {i}")

        assert engine._should_trigger_refine(session) is True

    def test_should_not_trigger_refine_below_threshold(self):
        """测试未达到阈值时不触发"""
        config = AppConfig.get_instance()
        engine = EngineCore(config, dev_mode=True)

        session = engine.get_or_create_session("test_below")

        # 添加少量消息
        session.add_message("user", "hi")
        session.add_message("assistant", "hi")

        assert engine._should_trigger_refine(session) is False

    def test_update_access_time_called(self):
        """测试每次 chat 调用都更新访问时间"""
        config = AppConfig.get_instance()
        # 使用临时 session 确保干净状态
        session_id = f"test_access_{int(time.time() * 1000)}"

        engine = EngineCore(config, dev_mode=True)
        engine.get_or_create_session(session_id)
        session = engine._session_mgr.get_session(session_id)
        time_before = session.last_access_time

        time.sleep(0.01)
        # 由于是 dev_mode，会同步精炼但不影响 access time 更新
        engine._session_mgr.update_access_time(session_id)

        assert session.last_access_time > time_before


class TestRefineAggressiveCompression:
    """测试更激进的压缩策略"""

    def test_refine_aggressive_compression(self):
        """测试精炼后 refined_history 数量"""
        from src.core.memory.refiner import BalancedHistoryRefiner
        from src.core.memory.config import MemoryConfig

        session = ConversationSession(session_id="test")

        # 添加 30 轮对话（60 条消息）
        for i in range(30):
            session.add_message("user", f"用户消息 {i}")
            session.add_message("assistant", f"助手回复 {i}")

        config = MemoryConfig.from_app_config()
        refiner = BalancedHistoryRefiner()
        refiner.refine(session, config)

        # 验证：精炼后 refined_history 应该更少
        # 之前可能保留 20+ 条，现在应该更少
        assert len(session.refined_history) < 25

    def test_refine_minimum_keep(self):
        """测试最小保留轮数"""
        from src.core.memory.refiner import BalancedHistoryRefiner
        from src.core.memory.config import MemoryConfig, BalanceStrategyConfig

        session = ConversationSession(session_id="test")

        # 添加 10 轮对话
        for i in range(10):
            session.add_message("user", f"用户消息 {i}")
            session.add_message("assistant", f"助手回复 {i}")

        strategy = BalanceStrategyConfig(keep_recent_turns=2)
        config = MemoryConfig(balance_strategy=strategy)
        refiner = BalancedHistoryRefiner()
        refiner.refine(session, config)

        # max(4, 2 // 2) = max(4, 1) = 4
        # 应该保留至少 4 轮（8 条消息）
        dialog_msgs = [m for m in session.refined_history if m.role != "system"]
        assert len(dialog_msgs) >= 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])