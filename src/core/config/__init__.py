"""
Core configuration module
"""
from .message_schemas import (
    BaseMessageSchema,
    DeepSeekSchema,
    MiniMaxSingleChatSchema,
    OllamaSchema,
    get_message_schema,
    SCHEMA_REGISTRY,
)

__all__ = [
    "BaseMessageSchema",
    "DeepSeekSchema",
    "MiniMaxSingleChatSchema",
    "OllamaSchema",
    "get_message_schema",
    "SCHEMA_REGISTRY",
]