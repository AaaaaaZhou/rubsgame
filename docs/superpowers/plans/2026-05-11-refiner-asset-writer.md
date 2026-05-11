# Refiner - AssetWriter 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Stage 3，将 WorldKnowledge / NPCProfile / Chapter 写入 assets/ 目录

**Architecture:** 与现有 AssetManager 写出一致，输出 YAML 文件到 assets/npc/、assets/world/、assets/plot/

**Tech Stack:** yaml, os, shutil

---

## File Structure

```
refiner/
├── writers/
│   ├── __init__.py  (Create)
│   └── asset_writer.py  (Create)
```

---

## Task 1: Create writers/__init__.py

**Files:**
- Create: `refiner/writers/__init__.py`

- [ ] **Step 1: 编写文件**

```python
"""Refiner writers package"""
from .asset_writer import AssetWriter

__all__ = ["AssetWriter"]
```

- [ ] **Step 2: Commit**

```bash
git add refiner/writers/__init__.py
git commit -m "feat(refiner): add writers package init"
```

---

## Task 2: 实现 AssetWriter

**Files:**
- Create: `refiner/writers/asset_writer.py`
- Test: `unittest/refiner/test_asset_writer.py`

- [ ] **Step 1: 编写测试文件**

```python
# unittest/refiner/test_asset_writer.py
import pytest
import os
import tempfile
import shutil
from unittest.mock import MagicMock
from refiner.writers.asset_writer import AssetWriter
from refiner.types import AnalysisResult, CharacterInfo, LocationInfo


def _make_mock_world():
    """创建模拟 WorldKnowledge"""
    from src.core.world_model import WorldKnowledge, Location, MemoryItem
    return WorldKnowledge(
        world_name="测试世界",
        global_memories=[MemoryItem(content="测试记忆", priority=8, tags=["test"])],
        locations=[Location(name="老街", description="test location", npcs=[], properties={})]
    )


def _make_mock_npcs():
    """创建模拟 NPCProfile 列表"""
    from src.core.persona import Persona, PersonaEmotionConfig
    from src.core.npc import NPCProfile

    persona1 = Persona(
        name="Alice",
        system_prompt="You are Alice",
        emotion_config=PersonaEmotionConfig(),
        raw_data={"name": "Alice", "gender": "女", "age": 17, "identity": "学生"}
    )
    profile1 = NPCProfile(persona=persona1, relationships={}, private_memories=[])

    persona2 = Persona(
        name="Bob",
        system_prompt="You are Bob",
        emotion_config=PersonaEmotionConfig(),
        raw_data={"name": "Bob", "gender": "男", "age": 18, "identity": "学生"}
    )
    profile2 = NPCProfile(persona=persona2, relationships={}, private_memories=[])

    return [profile1, profile2]


def _make_mock_chapters():
    """创建模拟 Chapter 列表"""
    from src.core.plot.types import Chapter, PlotNode, NodeType, NarrativeType

    node1 = PlotNode(
        id="n1",
        node_type=NodeType.NARRATION_ONLY,
        content="场景1描述",
        next="n2",
        narration_type=NarrativeType.SCENE_ENTER
    )
    node2 = PlotNode(
        id="n2",
        node_type=NodeType.DIALOGUE,
        npc_name="Alice",
        content="Alice说：你好",
        narration_type=NarrativeType.FREE_EXPLORE
    )

    chapter = Chapter(
        id="chapter_1",
        name="第一章",
        nodes=[node1, node2]
    )

    return [chapter]


def test_asset_writer_initialization():
    """测试 AssetWriter 初始化"""
    with tempfile.TemporaryDirectory() as tmpdir:
        writer = AssetWriter(tmpdir)
        assert writer._base_dir == tmpdir


def test_write_world_creates_file():
    """测试写出世界文件"""
    with tempfile.TemporaryDirectory() as tmpdir:
        writer = AssetWriter(tmpdir)
        world = _make_mock_world()

        writer.write_world(world)

        world_file = os.path.join(tmpdir, "world", "测试世界.yaml")
        assert os.path.exists(world_file)


def test_write_npcs_creates_directories():
    """测试写出 NPC 目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        writer = AssetWriter(tmpdir)
        npcs = _make_mock_npcs()

        writer.write_npcs(npcs)

        alice_dir = os.path.join(tmpdir, "npc", "Alice")
        bob_dir = os.path.join(tmpdir, "npc", "Bob")
        assert os.path.exists(alice_dir)
        assert os.path.exists(bob_dir)


def test_write_npc_creates_persona_yaml():
    """测试写出 NPC persona.yaml"""
    with tempfile.TemporaryDirectory() as tmpdir:
        writer = AssetWriter(tmpdir)
        npcs = _make_mock_npcs()

        writer.write_npcs(npcs)

        persona_file = os.path.join(tmpdir, "npc", "Alice", "persona.yaml")
        assert os.path.exists(persona_file)


def test_write_chapters_creates_directory():
    """测试写出章节目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        writer = AssetWriter(tmpdir)
        chapters = _make_mock_chapters()

        writer.write_chapters(chapters)

        chapter_dir = os.path.join(tmpdir, "plot", "chapter_1")
        assert os.path.exists(chapter_dir)


def test_write_chapter_creates_chapter_yaml():
    """测试写出 chapter.yaml"""
    with tempfile.TemporaryDirectory() as tmpdir:
        writer = AssetWriter(tmpdir)
        chapters = _make_mock_chapters()

        writer.write_chapters(chapters)

        chapter_file = os.path.join(tmpdir, "plot", "chapter_1", "chapter.yaml")
        assert os.path.exists(chapter_file)


def test_write_all():
    """测试完整写出流程"""
    with tempfile.TemporaryDirectory() as tmpdir:
        writer = AssetWriter(tmpdir)
        world = _make_mock_world()
        npcs = _make_mock_npcs()
        chapters = _make_mock_chapters()

        writer.write_all(world, npcs, chapters)

        # 验证世界文件
        assert os.path.exists(os.path.join(tmpdir, "world", "测试世界.yaml"))
        # 验证 NPC 目录
        assert os.path.exists(os.path.join(tmpdir, "npc", "Alice"))
        # 验证章节文件
        assert os.path.exists(os.path.join(tmpdir, "plot", "chapter_1", "chapter.yaml"))


def test_write_empty_npcs():
    """测试空 NPC 列表"""
    with tempfile.TemporaryDirectory() as tmpdir:
        writer = AssetWriter(tmpdir)
        writer.write_npcs([])
        # 不应创建 npc 目录
        npc_dir = os.path.join(tmpdir, "npc")
        assert not os.path.exists(npc_dir) or os.listdir(npc_dir) == []


def test_world_yaml_content():
    """验证世界 YAML 内容"""
    with tempfile.TemporaryDirectory() as tmpdir:
        writer = AssetWriter(tmpdir)
        world = _make_mock_world()

        writer.write_world(world)

        import yaml
        world_file = os.path.join(tmpdir, "world", "测试世界.yaml")
        with open(world_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert data["world_name"] == "测试世界"
        assert len(data["global_memories"]) >= 1
        assert len(data["locations"]) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest unittest/refiner/test_asset_writer.py -v`
Expected: FAIL (import error - module not found)

- [ ] **Step 3: 编写 AssetWriter 实现**

```python
"""
Stage 3: AssetWriter
将 WorldKnowledge / NPCProfile / Chapter 写入 assets/ 目录
"""
import os
import logging
from typing import List, Optional

import yaml

from ...src.core.world_model import WorldKnowledge
from ...src.core.npc import NPCProfile
from ...src.core.plot.types import Chapter

_logger = logging.getLogger("refiner.asset_writer")


class AssetWriter:
    """资源文件写出器 - Stage 3"""

    def __init__(self, base_dir: str = "assets"):
        self._base_dir = base_dir

    def write_all(
        self,
        world: Optional[WorldKnowledge],
        npcs: List[NPCProfile],
        chapters: List[Chapter]
    ):
        """写出所有资源

        Args:
            world: WorldKnowledge 或 None
            npcs: NPCProfile 列表
            chapters: Chapter 列表
        """
        if world:
            self.write_world(world)

        if npcs:
            self.write_npcs(npcs)

        if chapters:
            self.write_chapters(chapters)

        _logger.info(f"Wrote assets to {self._base_dir}")

    def write_world(self, world: WorldKnowledge):
        """写出世界文件

        Args:
            world: WorldKnowledge 对象
        """
        world_dir = os.path.join(self._base_dir, "world")
        os.makedirs(world_dir, exist_ok=True)

        world_file = os.path.join(world_dir, f"{world.world_name}.yaml")
        data = self._world_to_dict(world)

        with open(world_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)

        _logger.info(f"Wrote world to {world_file}")

    def write_npcs(self, npcs: List[NPCProfile]):
        """写出 NPC 目录

        Args:
            npcs: NPCProfile 列表
        """
        for npc in npcs:
            self._write_single_npc(npc)

    def write_chapters(self, chapters: List[Chapter]):
        """写出章节文件

        Args:
            chapters: Chapter 列表
        """
        for chapter in chapters:
            self._write_single_chapter(chapter)

    def _write_single_npc(self, npc: NPCProfile):
        """写出单个 NPC 目录"""
        npc_dir = os.path.join(self._base_dir, "npc", npc.persona.name)
        os.makedirs(npc_dir, exist_ok=True)

        # 写出 persona.yaml
        persona_data = self._persona_to_dict(npc.persona)
        persona_file = os.path.join(npc_dir, "persona.yaml")
        with open(persona_file, "w", encoding="utf-8") as f:
            yaml.dump(persona_data, f, allow_unicode=True, sort_keys=False)

        # 写出 relationships.yaml
        if npc.relationships:
            rel_data = {}
            for obj_id, rel in npc.relationships.items():
                rel_data[obj_id] = {
                    "subject_id": rel.subject_id,
                    "object_id": rel.object_id,
                    "relation_type": rel.relation_type,
                    "affinity": rel.affinity,
                    "trust": rel.trust,
                    "key_events": rel.key_events
                }
            rel_file = os.path.join(npc_dir, "relationships.yaml")
            with open(rel_file, "w", encoding="utf-8") as f:
                yaml.dump(rel_data, f, allow_unicode=True, sort_keys=False)

        # 写出 memories/ 目录
        if npc.private_memories:
            mem_dir = os.path.join(npc_dir, "memories")
            os.makedirs(mem_dir, exist_ok=True)

            for i, mem in enumerate(npc.private_memories):
                mem_data = {
                    "memory_id": mem.memory_id,
                    "owner_id": mem.owner_id,
                    "content": mem.content,
                    "memory_type": mem.memory_type,
                    "importance": mem.importance,
                    "emotional_valence": mem.emotional_valence,
                    "linked_to": mem.linked_to
                }
                mem_file = os.path.join(mem_dir, f"{mem.memory_id}.yaml")
                with open(mem_file, "w", encoding="utf-8") as f:
                    yaml.dump(mem_data, f, allow_unicode=True, sort_keys=False)

        _logger.info(f"Wrote NPC: {npc.persona.name}")

    def _write_single_chapter(self, chapter: Chapter):
        """写出单个章节"""
        chapter_dir = os.path.join(self._base_dir, "plot", chapter.id)
        os.makedirs(chapter_dir, exist_ok=True)

        data = self._chapter_to_dict(chapter)
        chapter_file = os.path.join(chapter_dir, "chapter.yaml")

        with open(chapter_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)

        _logger.info(f"Wrote chapter: {chapter.id}")

    def _world_to_dict(self, world: WorldKnowledge) -> dict:
        """将 WorldKnowledge 转换为 dict"""
        return {
            "world_name": world.world_name,
            "global_memories": [
                {
                    "content": mem.content,
                    "priority": mem.priority,
                    "tags": mem.tags
                }
                for mem in world.global_memories
            ],
            "locations": [
                {
                    "name": loc.name,
                    "description": loc.description,
                    "npcs": loc.npcs,
                    "properties": loc.properties
                }
                for loc in world.locations
            ]
        }

    def _persona_to_dict(self, persona) -> dict:
        """将 Persona 转换为 persona.yaml 格式"""
        raw = persona.raw_data if hasattr(persona, 'raw_data') else {}
        return {
            "name": raw.get("name", persona.name),
            "gender": raw.get("gender", ""),
            "age": raw.get("age"),
            "identity": raw.get("identity", ""),
            "basic_info": raw.get("basic_info", {}),
            "personality": raw.get("personality", {}),
            "behaviors": raw.get("behaviors", {}),
            "mood_system": raw.get("mood_system", {}),
            "background": raw.get("background", {}),
            "speech_style": raw.get("speech_style", {}),
            "topics_of_interest": raw.get("topics_of_interest", [])
        }

    def _chapter_to_dict(self, chapter: Chapter) -> dict:
        """将 Chapter 转换为 chapter.yaml 格式"""
        nodes_data = []
        for node in chapter.nodes:
            node_dict = {
                "id": node.id,
                "node_type": node.node_type.value if hasattr(node.node_type, 'value') else str(node.node_type),
                "content": node.content
            }

            if node.npc_name:
                node_dict["npc_name"] = node.npc_name

            if node.next:
                node_dict["next"] = node.next

            if node.branches:
                node_dict["branches"] = [
                    {
                        "id": b.id,
                        "label": b.label,
                        "condition": b.condition.__dict__ if b.condition else None,
                        "next_node": b.next_node
                    }
                    for b in node.branches
                ]

            if node.triggers:
                node_dict["triggers"] = [
                    {
                        "type": t.type.value if hasattr(t.type, 'value') else str(t.type),
                        "condition": t.condition.__dict__ if t.condition else None,
                        "event": t.event
                    }
                    for t in node.triggers
                ]

            if node.narration_type:
                node_dict["narration_type"] = node.narration_type.value if hasattr(node.narration_type, 'value') else str(node.narration_type)

            nodes_data.append(node_dict)

        data = {
            "chapter": {
                "id": chapter.id,
                "name": chapter.name
            },
            "nodes": nodes_data
        }

        # 添加 npc_interactions（如果存在）
        if hasattr(chapter, 'npc_interactions') and chapter.npc_interactions:
            interactions_data = []
            for interaction in chapter.npc_interactions:
                interactions_data.append({
                    "trigger_type": interaction.trigger.value if hasattr(interaction.trigger, 'value') else str(interaction.trigger),
                    "npc_name": interaction.npc_name,
                    "priority": interaction.priority,
                    "content": interaction.content,
                    "cooldown_turns": interaction.cooldown_turns
                })
            data["npc_interactions"] = interactions_data

        return data
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest unittest/refiner/test_asset_writer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add refiner/writers/asset_writer.py unittest/refiner/test_asset_writer.py
git commit -m "feat(refiner): add AssetWriter (Stage 3)"
```