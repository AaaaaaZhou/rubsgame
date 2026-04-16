"""
Logger Module Tests
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import pytest
from utils.logger import get_logger, LoggerFactory, _supports_ansi


def test_get_logger_returns_logger():
    logger = get_logger("test.namespace")
    assert logger is not None
    assert logger.name == "test.namespace"


def test_logger_factory_returns_consistent_instance():
    logger1 = LoggerFactory.get_logger("test.consistency")
    logger2 = LoggerFactory.get_logger("test.consistency")
    assert logger1 is logger2


def test_ansi_support_detection():
    result = _supports_ansi()
    assert isinstance(result, bool)


def test_logger_factory_getters():
    from utils.logger import get_emotion_logger, get_memory_logger, get_session_logger, get_llm_logger
    assert get_emotion_logger() is not None
    assert get_memory_logger() is not None
    assert get_session_logger() is not None
    assert get_llm_logger() is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
