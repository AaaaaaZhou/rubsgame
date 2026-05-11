# Refiner - 数据类型定义计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 定义 refiner 模块的所有数据结构，与现有 `src/core/types.py`、`src/core/npc.py`、`src/core/persona.py` 中的类型对齐

**Architecture:** 所有类型定义为纯 dataclass，不含业务逻辑，作为各 extractor 的数据传递载体

**Tech Stack:** Python dataclasses, typing

---

## File Structure

```
refiner/
├── types.py   (Create)
```

---

## Task 1: Create refiner/types.py

**Files:**
- Create: `refiner/types.py`

- [ ] **Step 1: 编写测试文件**

```python
# unittest/refiner/test_types.py
import pytest
from dataclasses import is_dataclass
from refiner.types import (
    AnalysisResult,
    CharacterInfo,
    LocationInfo,
    EventInfo,
    RelationshipInfo,
    RefinerOutput,
)


def test_character_info_fields():
    c = CharacterInfo(name="Alice", gender="女", age="17")
    assert c.name == "Alice"
    assert c.gender == "女"
    assert c.age == "17"


def test_location_info_default():
    loc = LocationInfo(name="老街")
    assert loc.name == "老街"
    assert loc.description == ""
    assert loc.properties == {}


def test_event_info_participants():
    e = EventInfo(scene_id="s1", description="两人在咖啡馆对话", participants=["Alice", "Bob"])
    assert len(e.participants) == 2


def test_analysis_result_empty():
    r = AnalysisResult(world_name="test", characters=[], locations=[], events=[], relationships=[])
    assert r.world_name == "test"
    assert len(r.characters) == 0


def test_refiner_output_defaults():
    from refiner.types import RefinerOutput
    o = RefinerOutput(npcs=[], chapters=[], analysis=None, warnings=[])
    assert len(o.npcs) == 0
    assert len(o.chapters) == 0
    assert o.warnings == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest unittest/refiner/test_types.py -v`
Expected: FAIL (import error - module not found)

- [ ] **Step 3: 编写 types.py**

```python
"""
Refiner 模块数据类型定义
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class CharacterInfo:
    """从文本提取的角色信息"""
    name: str
    gender: str = ""
    age: str = ""
    identity: str = ""
    personality_traits: List[str] = field(default_factory=list)
    speech_features: List[str] = field(default_factory=list)
    background_summary: str = ""
    appears_in_scenes: List[str] = field(default_factory=list)


@dataclass
class LocationInfo:
    """从文本提取的地点信息"""
    name: str
    description: str = ""
    properties: Dict[str, str] = field(default_factory=dict)


@dataclass
class EventInfo:
    """从文本提取的事件/场景信息"""
    scene_id: str
    description: str
    participants: List[str] = field(default_factory=list)
    location: str = ""
    event_type: str = ""  # dialogue / narration / action


@dataclass
class RelationshipInfo:
    """从文本提取的角色关系"""
    subject: str   # 角色A
    object: str     # 角色B
    relation_type: str = "stranger"
    affinity: int = 0
    trust: int = 50
    description: str = ""


@dataclass
class AnalysisResult:
    """TextAnalyzer 输出 - 四阶段提取的中间结果"""
    world_name: str
    characters: List[CharacterInfo] = field(default_factory=list)
    locations: List[LocationInfo] = field(default_factory=list)
    events: List[EventInfo] = field(default_factory=list)
    relationships: List[RelationshipInfo] = field(default_factory=list)


@dataclass
class RefinerOutput:
    """RefinerCore 最终输出"""
    world: Any = None  # WorldKnowledge, 允许 None
    npcs: List[Any] = field(default_factory=list)  # List[NPCProfile]
    chapters: List[Any] = field(default_factory=list)  # List[Chapter]
    analysis: Optional[AnalysisResult] = None
    warnings: List[str] = field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest unittest/refiner/test_types.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add refiner/types.py unittest/refiner/test_types.py
git commit -m "feat(refiner): add data types for refiner module"
```