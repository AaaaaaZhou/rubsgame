"""
Message Format Schemas for Different LLM Models

Each model may have different requirements for message format:
- Number of system messages (single vs multiple)
- Whether 'name' field is required
- Special role types supported
- Order of message elements
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseMessageSchema(ABC):
    """Base class for model-specific message schemas"""

    # Valid roles for this model
    VALID_ROLES: List[str] = ["system", "user", "assistant"]

    # Whether model supports multiple system messages
    SUPPORTS_MULTIPLE_SYSTEM: bool = True

    # Whether 'name' field is required for messages
    REQUIRES_NAME_FIELD: bool = False

    @abstractmethod
    def format_system_message(self, content: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Format a system message"""
        pass

    @abstractmethod
    def format_user_message(self, content: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Format a user message"""
        pass

    @abstractmethod
    def format_assistant_message(self, content: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Format an assistant message"""
        pass

    @abstractmethod
    def build_messages(
        self,
        system_content: str,
        history: List[Dict[str, Any]],
        user_input: str,
        npc_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Build complete message list for this model"""
        pass


class DeepSeekSchema(BaseMessageSchema):
    """Message schema for DeepSeek models"""

    SUPPORTS_MULTIPLE_SYSTEM = True
    REQUIRES_NAME_FIELD = False

    def format_system_message(self, content: str, name: Optional[str] = None) -> Dict[str, Any]:
        msg = {"role": "system", "content": content}
        if name:
            msg["name"] = name
        return msg

    def format_user_message(self, content: str, name: Optional[str] = None) -> Dict[str, Any]:
        msg = {"role": "user", "content": content}
        if name:
            msg["name"] = name
        return msg

    def format_assistant_message(self, content: str, name: Optional[str] = None) -> Dict[str, Any]:
        msg = {"role": "assistant", "content": content}
        if name:
            msg["name"] = name
        return msg

    def build_messages(
        self,
        system_content: str,
        history: List[Dict[str, Any]],
        user_input: str,
        npc_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        messages = [self.format_system_message(system_content)]
        messages.extend(history)
        messages.append(self.format_user_message(user_input))
        return messages


class MiniMaxSingleChatSchema(BaseMessageSchema):
    """Message schema for MiniMax M2-her single chat mode

    MiniMax single chat has restrictions:
    - Only ONE system message allowed
    - All context must be merged into single system message
    - name field is REQUIRED for all messages
    """
    SUPPORTS_MULTIPLE_SYSTEM = False
    REQUIRES_NAME_FIELD = True

    def format_system_message(self, content: str, name: Optional[str] = None) -> Dict[str, Any]:
        return {
            "role": "system",
            "name": name or "assistant",
            "content": content
        }

    def format_user_message(self, content: str, name: Optional[str] = None) -> Dict[str, Any]:
        return {
            "role": "user",
            "name": name or "user",
            "content": content
        }

    def format_assistant_message(self, content: str, name: Optional[str] = None) -> Dict[str, Any]:
        return {
            "role": "assistant",
            "name": name or "assistant",
            "content": content
        }

    def build_messages(
        self,
        system_content: str,
        history: List[Dict[str, Any]],
        user_input: str,
        npc_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Build messages for MiniMax single chat

        All context merged into ONE system message with name field.
        History uses assistant role with name field.
        """
        name = npc_name or "assistant"

        messages = [{
            "role": "system",
            "name": name,
            "content": system_content
        }]

        for msg in history:
            role = msg.get("role", "assistant")
            if role == "system":
                continue  # Skip system messages in history
            if role == "user":
                messages.append(self.format_user_message(msg["content"], "user"))
            else:
                messages.append(self.format_assistant_message(msg["content"], name))

        messages.append(self.format_user_message(user_input, "user"))
        return messages


class OllamaSchema(BaseMessageSchema):
    """Message schema for Ollama models (OpenAI-compatible)"""

    SUPPORTS_MULTIPLE_SYSTEM = True
    REQUIRES_NAME_FIELD = False

    def format_system_message(self, content: str, name: Optional[str] = None) -> Dict[str, Any]:
        msg = {"role": "system", "content": content}
        if name:
            msg["name"] = name
        return msg

    def format_user_message(self, content: str, name: Optional[str] = None) -> Dict[str, Any]:
        msg = {"role": "user", "content": content}
        if name:
            msg["name"] = name
        return msg

    def format_assistant_message(self, content: str, name: Optional[str] = None) -> Dict[str, Any]:
        msg = {"role": "assistant", "content": content}
        if name:
            msg["name"] = name
        return msg

    def build_messages(
        self,
        system_content: str,
        history: List[Dict[str, Any]],
        user_input: str,
        npc_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        messages = [self.format_system_message(system_content)]
        messages.extend(history)
        messages.append(self.format_user_message(user_input))
        return messages


# Schema registry
SCHEMA_REGISTRY: Dict[str, BaseMessageSchema] = {
    "deepseek_reasoner": DeepSeekSchema(),
    "deepseek_chat": DeepSeekSchema(),
    "minimax_m2_her": MiniMaxSingleChatSchema(),
    "minimax_m2.7": MiniMaxSingleChatSchema(),
    "llama3.2": OllamaSchema(),
}


def get_message_schema(model_name: str) -> BaseMessageSchema:
    """Get the appropriate message schema for a model"""
    # Try exact match first
    if model_name in SCHEMA_REGISTRY:
        return SCHEMA_REGISTRY[model_name]

    # Try prefix matching for variants
    for key, schema in SCHEMA_REGISTRY.items():
        if model_name.startswith(key):
            return schema

    # Default to DeepSeek schema (supports multiple system messages)
    return DeepSeekSchema()