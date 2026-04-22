"""
记忆提取模块
从对话历史中提取结构化记忆
"""
from abc import ABC, abstractmethod
from typing import List, Optional
import json
import re
import logging

from ..session import ConversationSession
from ..types import Message, MemoryItem
from ...clients.base import BaseLLMClient
from .config import MemoryConfig

_logger = logging.getLogger("rubsgame.memory.extractor")


class BaseMemoryExtractor(ABC):
    """记忆提取器抽象基类"""

    @abstractmethod
    def extract(
        self,
        session: ConversationSession,
        llm_client: Optional[BaseLLMClient] = None,
        config: Optional[MemoryConfig] = None
    ) -> List[MemoryItem]:
        """
        从会话历史中提取记忆

        Args:
            session: 会话对象
            llm_client: LLM 客户端（某些提取器可能不需要）
            config: 记忆配置

        Returns:
            提取的记忆项列表
        """
        pass


class LLMMemoryExtractor(BaseMemoryExtractor):
    """
    基于 LLM 的记忆提取器

    使用 LLM 分析 full_history，提取结构化记忆。
    记忆类型:
    - session_local: 写入 session.session_memories
    - world_global: 通过 AssetManager.update_global_memory() 更新到 WorldKnowledge
    """

    EXTRACTION_PROMPT = """你是一个记忆提取专家。请分析以下对话历史，提取关键信息并以 JSON 格式输出。

## 对话历史
{history_text}

## 输出要求
请提取最多 {max_memories} 条重要记忆，包括：
- 重要事件和决定
- 人物关系变化
- 地点和时间信息
- 角色情绪和状态
- 任务和目标

## 输出格式
```json
[
  {{
    "content": "记忆内容（简洁描述）",
    "memory_type": "session_local" 或 "world_global",
    "priority": 优先级(0-10),
    "tags": ["标签1", "标签2"]
  }}
]
```

注意：
- session_local: 仅与当前会话相关，不影响世界观
- world_global: 具有全局重要性，应更新到世界观知识库
- priority 越高表示越重要
- 只提取真正重要的信息，避免冗余
"""

    def __init__(self, extraction_model: str = "deepseek_reasoner"):
        self._extraction_model = extraction_model

    def extract(
        self,
        session: ConversationSession,
        llm_client: Optional[BaseLLMClient] = None,
        config: Optional[MemoryConfig] = None
    ) -> List[MemoryItem]:
        """使用 LLM 提取记忆"""
        if llm_client is None:
            _logger.warning("No LLM client provided, falling back to rule-based extraction")
            return self._rule_based_extract(session, config)

        if config is None:
            config = MemoryConfig()

        # 1. 构建历史文本
        history_text = self._format_history_for_extraction(session.full_history)

        # 2. 构建 Prompt
        max_memories = config.max_memories_per_extraction
        prompt = self.EXTRACTION_PROMPT.format(
            history_text=history_text,
            max_memories=max_memories
        )

        # 3. 调用 LLM
        try:
            response = llm_client.chat([{"role": "user", "content": prompt}])

            # 4. 解析响应
            memories = self._parse_llm_response(response)

            # 5. 过滤低优先级记忆
            memories = [
                m for m in memories
                if m.priority >= config.memory_priority_threshold
            ]

            _logger.info(
                f"LLMMemoryExtractor: extracted {len(memories)} memories, "
                f"session={session.session_id}"
            )

            return memories

        except Exception as e:
            _logger.error(f"LLM extraction failed: {e}, falling back to rule-based")
            return self._rule_based_extract(session, config)

    def _format_history_for_extraction(self, messages: List[Message]) -> str:
        """将消息列表格式化为可读的历史文本"""
        lines = []
        for msg in messages:
            role_label = {"system": "[系统]", "user": "[用户]", "assistant": "[助手]"}.get(msg.role, f"[{msg.role}]")
            content = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
            lines.append(f"{role_label} {content}")
        return "\n\n".join(lines)

    def _parse_llm_response(self, response: str) -> List[MemoryItem]:
        """解析 LLM 返回的 JSON 记忆列表"""
        json_str = self._extract_json(response)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            _logger.warning(f"Failed to parse JSON from LLM response: {response[:200]}")
            return []

        if not isinstance(data, list):
            if isinstance(data, dict) and "memories" in data:
                data = data["memories"]
            else:
                return []

        memories = []
        for item in data:
            try:
                memory = MemoryItem(
                    content=item["content"],
                    memory_type=item.get("memory_type", "session_local"),
                    priority=int(item.get("priority", 5)),
                    tags=item.get("tags", [])
                )
                memories.append(memory)
            except (KeyError, ValueError) as e:
                _logger.warning(f"Skipping invalid memory item: {item}, error: {e}")
                continue

        return memories

    def _extract_json(self, text: str) -> str:
        """从文本中提取 JSON 字符串"""
        match = re.search(r"```json\s*(\[.*?\])\s*```", text, re.DOTALL)
        if match:
            return match.group(1)
        match = re.search(r"(\[.*\])", text, re.DOTALL)
        if match:
            return match.group(1)
        return text

    def _rule_based_extract(
        self,
        session: ConversationSession,
        config: Optional[MemoryConfig] = None
    ) -> List[MemoryItem]:
        """基于规则的简单记忆提取（备用方案）"""
        if config is None:
            config = MemoryConfig()

        memories: List[MemoryItem] = []
        keywords = ["记住", "重要", "决定", "喜欢", "讨厌", "承诺", "任务"]

        for msg in session.full_history:
            if msg.role != "user":
                continue
            content = msg.content
            for keyword in keywords:
                if keyword in content:
                    sentences = content.split("。")
                    for sent in sentences:
                        if keyword in sent and len(sent) > 10:
                            memories.append(MemoryItem(
                                content=sent.strip(),
                                memory_type="session_local",
                                priority=5,
                                tags=["extracted", keyword]
                            ))
                            break
                    break

        seen = set()
        unique_memories = [m for m in memories if m.content not in seen and not seen.add(m.content)]
        return unique_memories[:config.max_memories_per_extraction]


class RuleBasedMemoryExtractor(BaseMemoryExtractor):
    """基于规则的简单记忆提取器（不需要 LLM）"""

    def __init__(self):
        self._keywords = {
            "important": ["重要", "关键", "记住", "必须"],
            "decision": ["决定", "选择", "计划", "要"],
            "emotion": ["喜欢", "讨厌", "爱", "恨", "开心", "难过"],
            "task": ["任务", "目标", "要做", "需要"],
        }

    def extract(
        self,
        session: ConversationSession,
        llm_client: Optional[BaseLLMClient] = None,
        config: Optional[MemoryConfig] = None
    ) -> List[MemoryItem]:
        """基于规则提取记忆"""
        if config is None:
            config = MemoryConfig()

        memories: List[MemoryItem] = []

        for msg in session.full_history:
            if msg.role not in ("user", "assistant"):
                continue

            content = msg.content

            for category, keywords in self._keywords.items():
                for keyword in keywords:
                    if keyword in content:
                        sentences = content.replace("!", "。").replace("?", "。").split("。")
                        for sent in sentences:
                            if keyword in sent and 10 < len(sent) < 200:
                                memories.append(MemoryItem(
                                    content=sent.strip(),
                                    memory_type="session_local",
                                    priority=self._estimate_priority(category, keyword),
                                    tags=[category, keyword]
                                ))
                        break

        seen = set()
        unique_memories = [m for m in memories if m.content not in seen and not seen.add(m.content)]
        return unique_memories[:config.max_memories_per_extraction]

    def _estimate_priority(self, category: str, keyword: str) -> int:
        priority_map = {"important": 8, "decision": 7, "task": 6, "emotion": 5}
        return priority_map.get(category, 5)