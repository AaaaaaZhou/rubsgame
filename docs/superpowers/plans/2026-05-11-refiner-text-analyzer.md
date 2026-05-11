# Refiner - TextAnalyzer 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Stage 1，从原始 .txt 文本中提取角色、地点、事件、关系

**Architecture:** 通过多轮 LLM 调用逐步提取信息，使用 ClientManager 调用 LLM，支持 model 配置

**Tech Stack:** ClientManager, yaml, re (JSON 提取)

---

## File Structure

```
refiner/
├── extractors/
│   ├── __init__.py  (Create)
│   └── text_analyzer.py  (Create)
```

---

## Task 1: Create extractors/__init__.py

**Files:**
- Create: `refiner/extractors/__init__.py`

- [ ] **Step 1: 编写文件**

```python
"""Refiner extractors package"""
from .text_analyzer import TextAnalyzer

__all__ = ["TextAnalyzer"]
```

- [ ] **Step 2: Commit**

```bash
git add refiner/extractors/__init__.py
git commit -m "feat(refiner): add extractors package init"
```

---

## Task 2: 实现 TextAnalyzer

**Files:**
- Create: `refiner/extractors/text_analyzer.py`
- Test: `unittest/refiner/test_text_analyzer.py`

- [ ] **Step 1: 编写测试文件**

```python
# unittest/refiner/test_text_analyzer.py
import pytest
from unittest.mock import MagicMock, patch
from refiner.extractors.text_analyzer import TextAnalyzer
from refiner.types import AnalysisResult, CharacterInfo, LocationInfo


class MockClient:
    """模拟 ClientManager.get_client() 返回的对象"""
    def __init__(self, response_text: str):
        self._response = response_text

    def chat(self, messages, **kwargs):
        return MagicMock(content=self._response)


def test_text_analyzer_initialization():
    mock_mgr = MagicMock()
    analyzer = TextAnalyzer(mock_mgr)
    assert analyzer._client_mgr is mock_mgr
    assert analyzer._model_name is None


def test_text_analyzer_with_model():
    mock_mgr = MagicMock()
    analyzer = TextAnalyzer(mock_mgr, model_name="deepseek_reasoner")
    assert analyzer._model_name == "deepseek_reasoner"


def test_extract_world_name_and_global():
    """测试 Step 1 - 提取世界名称和全局记忆"""
    mock_mgr = MagicMock()
    analyzer = TextAnalyzer(mock_mgr)

    # 模拟 LLM 返回
    mock_response = """{"world_name": "清溪镇", "global_summary": "西南河谷小城，民风质朴", "locations": [{"name": "老街", "description": "历史悠久的商业街"}, {"name": "清溪河", "description": "穿城而过的小河"}], "characters": [{"name": "Alice", "gender": "女", "age": "17", "identity": "高中学生", "personality_traits": ["温和", "内向"], "speech_features": ["说话轻柔"], "background_summary": "在小镇长大"}, {"name": "Bob", "gender": "男", "age": "18", "identity": "高中学生", "personality_traits": ["外向", "开朗"], "speech_features": ["说话直接"], "background_summary": "喜欢户外活动"}], "events": [{"scene_id": "e1", "description": "Alice在老街咖啡馆遇到Bob", "participants": ["Alice", "Bob"], "location": "老街咖啡馆", "event_type": "dialogue"}, {"scene_id": "e2", "description": "两人决定去清溪河边散步", "participants": ["Alice", "Bob"], "location": "清溪河", "event_type": "action"}], "relationships": [{"subject": "Alice", "object": "Bob", "relation_type": "stranger", "affinity": 0, "trust": 50, "description": "初次见面"}]}"""

    mock_client = MagicMock()
    mock_client.chat.return_value = MagicMock(content=mock_response)
    mock_mgr.get_client.return_value = mock_client

    text = "Alice和Bob在老街咖啡馆相遇，Bob邀请Alice去清溪河边散步。"
    result = analyzer.extract(text)

    assert isinstance(result, AnalysisResult)
    assert result.world_name == "清溪镇"
    assert len(result.characters) >= 2
    assert len(result.locations) >= 2
    assert len(result.events) >= 1
    assert len(result.relationships) >= 1


def test_extract_with_empty_text():
    """测试空文本处理"""
    mock_mgr = MagicMock()
    analyzer = TextAnalyzer(mock_mgr)

    mock_client = MagicMock()
    mock_client.chat.return_value = MagicMock(content='{"world_name": "", "characters": [], "locations": [], "events": [], "relationships": []}')
    mock_mgr.get_client.return_value = mock_client

    result = analyzer.extract("")
    assert result.world_name == ""
    assert len(result.characters) == 0


def test_parse_json_response_valid():
    """测试 JSON 解析 - 有效输入"""
    mock_mgr = MagicMock()
    analyzer = TextAnalyzer(mock_mgr)

    json_str = '{"world_name": "test", "characters": []}'
    result = analyzer._parse_json_response(json_str)

    assert result["world_name"] == "test"


def test_parse_json_response_with_markdown():
    """测试 JSON 解析 - 带 markdown 包装"""
    mock_mgr = MagicMock()
    analyzer = TextAnalyzer(mock_mgr)

    json_str = '```json\n{"world_name": "test", "characters": []}\n```'
    result = analyzer._parse_json_response(json_str)

    assert result["world_name"] == "test"


def test_parse_json_response_invalid():
    """测试 JSON 解析 - 无效输入回退"""
    mock_mgr = MagicMock()
    analyzer = TextAnalyzer(mock_mgr)

    result = analyzer._parse_json_response("not json at all")
    # 应该返回包含原文本的 fallback
    assert isinstance(result, dict)


def test_character_info_dataclass():
    """验证 CharacterInfo 字段"""
    from refiner.types import CharacterInfo
    c = CharacterInfo(
        name="Alice",
        gender="女",
        age="17",
        identity="学生",
        personality_traits=["温和"],
        speech_features=["轻柔"],
        background_summary="test"
    )
    assert c.name == "Alice"
    assert "温和" in c.personality_traits


def test_location_info_dataclass():
    """验证 LocationInfo 字段"""
    from refiner.types import LocationInfo
    loc = LocationInfo(name="老街", description="test", properties={"type": "street"})
    assert loc.name == "老街"
    assert loc.properties["type"] == "street"


def test_event_info_dataclass():
    """验证 EventInfo 字段"""
    from refiner.types import EventInfo
    e = EventInfo(scene_id="e1", description="test", participants=["A", "B"], location="老街", event_type="dialogue")
    assert e.scene_id == "e1"
    assert e.event_type == "dialogue"
    assert len(e.participants) == 2


def test_relationship_info_dataclass():
    """验证 RelationshipInfo 字段"""
    from refiner.types import RelationshipInfo
    r = RelationshipInfo(subject="A", object="B", relation_type="friend", affinity=50, trust=70)
    assert r.relation_type == "friend"
    assert r.affinity == 50
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest unittest/refiner/test_text_analyzer.py -v`
Expected: FAIL (import error - module not found)

- [ ] **Step 3: 编写 TextAnalyzer 实现**

```python
"""
Stage 1: TextAnalyzer
从原始文本中提取角色、地点、事件、关系
"""
import json
import logging
from typing import Optional

from ...clients.manager import ClientManager
from ..types import (
    AnalysisResult, CharacterInfo, LocationInfo,
    EventInfo, RelationshipInfo
)

_logger = logging.getLogger("refiner.text_analyzer")

SYSTEM_PROMPT = """你是一个故事分析助手。请分析输入的文本，提取以下信息并以 JSON 格式输出：

{
  "world_name": "世界/故事发生的地点名称",
  "global_summary": "描述该世界的整体氛围和特点（1-2句）",
  "characters": [
    {
      "name": "角色姓名",
      "gender": "男/女/其他",
      "age": "年龄或年龄段",
      "identity": "社会身份（如学生、教师）",
      "personality_traits": ["性格特征1", "性格特征2"],
      "speech_features": ["语言/说话特点"],
      "background_summary": "背景简介（1句）"
    }
  ],
  "locations": [
    {
      "name": "地点名称",
      "description": "简短描述（1-2句）"
    }
  ],
  "events": [
    {
      "scene_id": "场景ID（如 e1, e2）",
      "description": "场景描述",
      "participants": ["角色1", "角色2"],
      "location": "发生的地点",
      "event_type": "dialogue/narration/action"
    }
  ],
  "relationships": [
    {
      "subject": "角色A",
      "object": "角色B",
      "relation_type": "stranger/friend/rival/family/... ",
      "affinity": 数字（-100到100，默认0）,
      "trust": 数字（0到100，默认50）,
      "description": "关系描述（1句）"
    }
  ]
}

请确保输出是有效的 JSON，不要包含 markdown 代码块或其他文本。"""


class TextAnalyzer:
    """文本分析器 - Stage 1"""

    def __init__(
        self,
        client_manager: ClientManager,
        model_name: Optional[str] = None
    ):
        self._client_mgr = client_manager
        self._model_name = model_name

    def extract(self, text: str) -> AnalysisResult:
        """分析文本并提取结构化信息

        Args:
            text: 原始文本输入

        Returns:
            AnalysisResult 对象
        """
        if not text or not text.strip():
            return AnalysisResult(
                world_name="",
                characters=[],
                locations=[],
                events=[],
                relationships=[]
            )

        # 调用 LLM 进行分析
        response_text = self._call_llm(text)
        parsed = self._parse_json_response(response_text)

        # 转换为 dataclass
        return self._build_analysis_result(parsed)

    def _call_llm(self, text: str) -> str:
        """调用 LLM"""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ]

        client = self._client_mgr.get_client(self._model_name)
        response = client.chat(messages)
        return response.content

    def _parse_json_response(self, text: str) -> dict:
        """从 LLM 输出中解析 JSON"""
        import re

        # 尝试提取 ```json ... ``` 块
        match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            json_str = match.group(1)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        # 尝试提取第一个 { ... }
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            json_str = match.group(1)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        # 回退：返回包含 world_name 的默认结构
        _logger.warning("Failed to parse JSON response, using fallback")
        return {
            "world_name": "",
            "characters": [],
            "locations": [],
            "events": [],
            "relationships": []
        }

    def _build_analysis_result(self, parsed: dict) -> AnalysisResult:
        """将解析结果转换为 AnalysisResult"""
        characters = []
        for c in parsed.get("characters", []):
            characters.append(CharacterInfo(
                name=c.get("name", ""),
                gender=c.get("gender", ""),
                age=c.get("age", ""),
                identity=c.get("identity", ""),
                personality_traits=c.get("personality_traits", []),
                speech_features=c.get("speech_features", []),
                background_summary=c.get("background_summary", ""),
                appears_in_scenes=[]
            ))

        locations = []
        for loc in parsed.get("locations", []):
            locations.append(LocationInfo(
                name=loc.get("name", ""),
                description=loc.get("description", ""),
                properties={}
            ))

        events = []
        for e in parsed.get("events", []):
            events.append(EventInfo(
                scene_id=e.get("scene_id", ""),
                description=e.get("description", ""),
                participants=e.get("participants", []),
                location=e.get("location", ""),
                event_type=e.get("event_type", "")
            ))

        relationships = []
        for r in parsed.get("relationships", []):
            relationships.append(RelationshipInfo(
                subject=r.get("subject", ""),
                object=r.get("object", ""),
                relation_type=r.get("relation_type", "stranger"),
                affinity=r.get("affinity", 0),
                trust=r.get("trust", 50),
                description=r.get("description", "")
            ))

        return AnalysisResult(
            world_name=parsed.get("world_name", ""),
            characters=characters,
            locations=locations,
            events=events,
            relationships=relationships
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest unittest/refiner/test_text_analyzer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add refiner/extractors/text_analyzer.py unittest/refiner/test_text_analyzer.py
git commit -m "feat(refiner): add TextAnalyzer (Stage 1)"
```