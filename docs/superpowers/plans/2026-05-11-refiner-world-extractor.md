# Refiner - WorldExtractor 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Stage 2a，将 TextAnalyzer 的 AnalysisResult 转换为 WorldKnowledge 对象

**Architecture:** 与现有 WorldLoader 输出同规格，支持增量合并现有世界

**Tech Stack:** ClientManager, WorldKnowledge, WorldModel types

---

## File Structure

```
refiner/
├── extractors/
│   └── world_extractor.py  (Create)
```

---

## Task 1: 实现 WorldExtractor

**Files:**
- Create: `refiner/extractors/world_extractor.py`
- Test: `unittest/refiner/test_world_extractor.py`

- [ ] **Step 1: 编写测试文件**

```python
# unittest/refiner/test_world_extractor.py
import pytest
from unittest.mock import MagicMock
from refiner.extractors.world_extractor import WorldExtractor
from refiner.types import AnalysisResult, CharacterInfo, LocationInfo, EventInfo


def _make_analysis_result():
    """创建测试用 AnalysisResult"""
    return AnalysisResult(
        world_name="清溪镇",
        characters=[
            CharacterInfo(name="Alice", gender="女", age="17"),
            CharacterInfo(name="Bob", gender="男", age="18"),
        ],
        locations=[
            LocationInfo(
                name="老街",
                description="历史悠久的商业街，两侧店铺密集",
                properties={"type": "commercial_street", "district": "old_town"}
            ),
            LocationInfo(
                name="清溪河",
                description="穿城而过的小河，河岸两侧有柳树",
                properties={"type": "natural_water"}
            ),
        ],
        events=[
            EventInfo(scene_id="e1", description="Alice在老街遇到Bob", participants=["Alice", "Bob"], location="老街", event_type="dialogue"),
        ],
        relationships=[]
    )


def test_world_extractor_initialization():
    """测试 WorldExtractor 初始化"""
    mock_client_mgr = MagicMock()
    extractor = WorldExtractor(mock_client_mgr)
    assert extractor._client_mgr is mock_client_mgr
    assert extractor._model_name is None


def test_world_extractor_with_model():
    """测试带 model_name 的初始化"""
    mock_client_mgr = MagicMock()
    extractor = WorldExtractor(mock_client_mgr, model_name="deepseek_reasoner")
    assert extractor._model_name == "deepseek_reasoner"


def test_build_basic_world():
    """测试从 AnalysisResult 构建基础 WorldKnowledge"""
    mock_client_mgr = MagicMock()
    extractor = WorldExtractor(mock_client_mgr)

    analysis = _make_analysis_result()
    world = extractor.build(analysis)

    assert world.world_name == "清溪镇"
    assert len(world.global_memories) >= 1
    assert len(world.locations) == 2


def test_build_with_empty_analysis():
    """测试空 AnalysisResult"""
    mock_client_mgr = MagicMock()
    extractor = WorldExtractor(mock_client_mgr)

    analysis = AnalysisResult(world_name="", characters=[], locations=[], events=[], relationships=[])
    world = extractor.build(analysis)

    assert world.world_name == ""
    assert len(world.locations) == 0


def test_build_with_locations_only():
    """测试只有地点的情况"""
    mock_client_mgr = MagicMock()
    extractor = WorldExtractor(mock_client_mgr)

    analysis = AnalysisResult(
        world_name="测试世界",
        characters=[],
        locations=[
            LocationInfo(name="咖啡馆", description="老街深处的一家小咖啡馆"),
        ],
        events=[],
        relationships=[]
    )
    world = extractor.build(analysis)

    assert world.world_name == "测试世界"
    assert len(world.locations) == 1
    assert world.locations[0].name == "咖啡馆"


def test_location_properties_preserved():
    """测试地点属性被正确保留"""
    mock_client_mgr = MagicMock()
    extractor = WorldExtractor(mock_client_mgr)

    analysis = _make_analysis_result()
    world = extractor.build(analysis)

    # 找到老街
    old_street = next((loc for loc in world.locations if loc.name == "老街"), None)
    assert old_street is not None
    assert old_street.properties.get("type") == "commercial_street"
    assert old_street.properties.get("district") == "old_town"


def test_global_memory_generated():
    """测试全局记忆生成"""
    mock_client_mgr = MagicMock()
    extractor = WorldExtractor(mock_client_mgr)

    analysis = _make_analysis_result()
    world = extractor.build(analysis)

    assert len(world.global_memories) >= 1
    # global_memories 应该有 content 和 priority
    for mem in world.global_memories:
        assert hasattr(mem, 'content')
        assert hasattr(mem, 'priority')


def test_world_merge_existing():
    """测试与现有世界合并"""
    mock_client_mgr = MagicMock()
    extractor = WorldExtractor(mock_client_mgr)

    from src.core.world_model import WorldKnowledge, Location, MemoryItem

    existing = WorldKnowledge(
        world_name="清溪镇",
        global_memories=[MemoryItem(content="已有记忆", priority=9, tags=[])],
        locations=[Location(name="图书馆", description="老城区边缘的图书馆", npcs=[], properties={})]
    )

    analysis = _make_analysis_result()
    merged = extractor.merge_existing(existing, analysis)

    # 应该有原有的 + 新分析的
    assert len(merged.global_memories) >= 2
    assert len(merged.locations) >= 3  # 原有1个 + 分析2个


def test_world_get_system_context():
    """测试 WorldKnowledge.get_system_context() 可用"""
    mock_client_mgr = MagicMock()
    extractor = WorldExtractor(mock_client_mgr)

    analysis = _make_analysis_result()
    world = extractor.build(analysis)

    ctx = world.get_system_context()
    assert isinstance(ctx, str)
    assert len(ctx) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest unittest/refiner/test_world_extractor.py -v`
Expected: FAIL (import error - module not found)

- [ ] **Step 3: 编写 WorldExtractor 实现**

```python
"""
Stage 2a: WorldExtractor
将 AnalysisResult 转换为 WorldKnowledge 对象
"""
import logging
from typing import Optional

from ...clients.manager import ClientManager
from ...src.core.world_model import WorldKnowledge, Location, MemoryItem
from ..types import AnalysisResult, LocationInfo

_logger = logging.getLogger("refiner.world_extractor")


class WorldExtractor:
    """世界观提取器 - Stage 2a"""

    def __init__(
        self,
        client_manager: ClientManager,
        model_name: Optional[str] = None
    ):
        self._client_mgr = client_manager
        self._model_name = model_name

    def build(self, analysis: AnalysisResult) -> WorldKnowledge:
        """从 AnalysisResult 构建 WorldKnowledge

        Args:
            analysis: TextAnalyzer 输出

        Returns:
            WorldKnowledge 对象
        """
        if not analysis.world_name:
            world_name = "未命名世界"
        else:
            world_name = analysis.world_name

        # 构建全局记忆
        global_memories = self._build_global_memories(analysis)

        # 构建地点列表
        locations = self._build_locations(analysis)

        world = WorldKnowledge(
            world_name=world_name,
            global_memories=global_memories,
            locations=locations
        )

        _logger.info(f"Built WorldKnowledge: {world_name}, {len(locations)} locations")
        return world

    def merge_existing(
        self,
        existing: WorldKnowledge,
        analysis: AnalysisResult
    ) -> WorldKnowledge:
        """与现有世界合并（不覆盖已有数据）

        Args:
            existing: 现有的 WorldKnowledge
            analysis: 新分析结果

        Returns:
            合并后的 WorldKnowledge
        """
        # 保留原有的全局记忆
        merged_memories = list(existing.global_memories)

        # 添加分析产生的新记忆
        new_memories = self._build_global_memories(analysis)
        existing_ids = {m.content[:50] for m in merged_memories}
        for mem in new_memories:
            if mem.content[:50] not in existing_ids:
                merged_memories.append(mem)

        # 合并地点（按名称去重）
        existing_names = {loc.name for loc in existing.locations}
        merged_locations = list(existing.locations)

        for loc in self._build_locations(analysis):
            if loc.name not in existing_names:
                merged_locations.append(loc)

        return WorldKnowledge(
            world_name=existing.world_name,
            global_memories=merged_memories,
            locations=merged_locations
        )

    def _build_global_memories(self, analysis: AnalysisResult) -> list:
        """从分析结果构建全局记忆"""
        memories = []

        # 世界概述记忆
        if analysis.world_name:
            memories.append(MemoryItem(
                content=f"{analysis.world_name}是一个故事发生的世界",
                priority=8,
                tags=["world_overview"]
            ))

        # 从事件中提取全局记忆
        if analysis.events:
            event_count = len(analysis.events)
            memories.append(MemoryItem(
                content=f"故事包含{event_count}个场景事件",
                priority=6,
                tags=["story_structure"]
            ))

        # 从关系中提取全局记忆
        if analysis.relationships:
            chars = set()
            for rel in analysis.relationships:
                chars.add(rel.subject)
                chars.add(rel.object)
            memories.append(MemoryItem(
                content=f"涉及{len(chars)}个角色",
                priority=5,
                tags=["character_overview"]
            ))

        return memories

    def _build_locations(self, analysis: AnalysisResult) -> list:
        """从分析结果构建地点列表"""
        locations = []

        for loc_info in analysis.locations:
            if not loc_info.name:
                continue

            loc = Location(
                name=loc_info.name,
                description=loc_info.description or "",
                npcs=[],
                properties=dict(loc_info.properties) if loc_info.properties else {}
            )
            locations.append(loc)

        return locations
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest unittest/refiner/test_world_extractor.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add refiner/extractors/world_extractor.py unittest/refiner/test_world_extractor.py
git commit -m "feat(refiner): add WorldExtractor (Stage 2a)"
```