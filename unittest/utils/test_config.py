"""
Config Module Tests
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import pytest
from utils.config import config


def test_config_loads_models():
    models = config.get_available_models()
    assert len(models) > 0, "No LLM models loaded"
    assert "deepseek_reasoner" in models


def test_config_default_model():
    assert config.default_llm_model == "minimax_m2_her"


def test_config_refine_model():
    assert config.refine_llm_model == "deepseek_reasoner"


def test_config_get_llm_config():
    llm_config = config.get_llm_config("deepseek_reasoner")
    assert llm_config.get("base_url") == "https://api.deepseek.com"
    assert llm_config.get("model") == "deepseek-reasoner"


def test_config_get_available_models():
    models = config.get_available_models()
    assert isinstance(models, list)
    assert len(models) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
