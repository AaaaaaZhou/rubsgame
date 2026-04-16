"""
LLM Connection Tests
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import pytest
from openai import OpenAI
from utils.config import config
from utils.logger import get_logger

_logger = get_logger("rubsgame.test.llm")


def test_deepseek_reasoner_connection():
    model_name = "deepseek_reasoner"
    llm_config = config.get_llm_config(model_name)

    api_key = llm_config.get("api_key")
    assert api_key, f"API key not configured for {model_name}"

    client = OpenAI(api_key=api_key, base_url=llm_config.get("base_url"))

    response = client.chat.completions.create(
        model=llm_config.get("model", model_name),
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Reply with exactly: 'Connection successful' if you can hear me."}
        ],
        max_tokens=llm_config.get("max_tokens", 1024),
        temperature=llm_config.get("temperature", 0.7)
    )

    content = response.choices[0].message.content
    assert content and len(content.strip()) > 0, "Empty response from LLM"
    _logger.info(f"Response: {content}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
