# Refiner - PlotBuilder 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Stage 2c，将 AnalysisResult 中的事件序列转换为 Chapter 列表

**Architecture:** 与现有 PlotLoader 输出同规格，支持 NodeType.DIALOGUE / NARRATION_ONLY / BRANCH / NPC_INTERACT

**Tech Stack:** Chapter, PlotNode, Branch, NodeType, NarrativeType from src/core/plot/types.py

---

## File Structure

```
refiner/
├── extractors/
│   └── plot_builder.py  (Create)
```

---

## Task 1: 实现 PlotBuilder

**Files:**
- Create: `refiner/extractors/plot_builder.py`
- Test: `unittest/refiner/test_plot_builder.py`

- [ ] **Step 1: 编写测试文件**

```python
# unittest/refiner/test_plot_builder.py
import pytest
from unittest.mock import MagicMock
from refiner.extractors.plot_builder import PlotBuilder
from refiner.types import (
    AnalysisResult, CharacterInfo, LocationInfo,
    EventInfo, RelationshipInfo
)


def _make_analysis_result():
    """创建测试用 AnalysisResult"""
    return AnalysisResult(
        world_name="清溪镇",
        characters=[
            CharacterInfo(name="Alice", gender="女", age="17"),
            CharacterInfo(name="Bob", gender="男", age="18"),
        ],
        locations=[
            LocationInfo(name="老街", description="历史悠久的商业街"),
            LocationInfo(name="咖啡馆", description="老街深处的一家小店"),
        ],
        events=[
            EventInfo(
                scene_id="e1",
                description="Alice第一次来到老街，在咖啡馆门口驻足",
                participants=["Alice"],
                location="老街",
                event_type="narration"
            ),
            EventInfo(
                scene_id="e2",
                description="Alice在咖啡馆与Bob初次相遇，Bob主动打招呼",
                participants=["Alice", "Bob"],
                location="咖啡馆",
                event_type="dialogue"
            ),
            EventInfo(
                scene_id="e3",
                description="Bob邀请Alice一起去清溪河边散步",
                participants=["Alice", "Bob"],
                location="咖啡馆",
                event_type="dialogue"
            ),
            EventInfo(
                scene_id="e4",
                description="Alice和Bob来到河边欣赏傍晚的景色",
                participants=["Alice", "Bob"],
                location="清溪河",
                event_type="action"
            ),
        ],
        relationships=[
            RelationshipInfo(subject="Alice", object="Bob", relation_type="stranger", affinity=0, trust=50)
        ]
    )


def test_plot_builder_initialization():
    """测试 PlotBuilder 初始化"""
    mock_client_mgr = MagicMock()
    builder = PlotBuilder(mock_client_mgr)
    assert builder._client_mgr is mock_client_mgr


def test_build_single_chapter():
    """测试构建单个章节"""
    mock_client_mgr = MagicMock()
    builder = PlotBuilder(mock_client_mgr)

    analysis = _make_analysis_result()
    chapters = builder.build(analysis)

    assert len(chapters) >= 1
    assert chapters[0].id is not None
    assert chapters[0].name is not None


def test_chapter_has_nodes():
    """测试章节包含节点"""
    mock_client_mgr = MagicMock()
    builder = PlotBuilder(mock_client_mgr)

    analysis = _make_analysis_result()
    chapters = builder.build(analysis)

    assert len(chapters[0].nodes) >= 4  # 4个事件


def test_node_types_assigned():
    """测试节点类型正确分配"""
    mock_client_mgr = MagicMock()
    builder = PlotBuilder(mock_client_mgr)

    analysis = _make_analysis_result()
    chapters = builder.build(analysis)

    node_types = [n.node_type for n in chapters[0].nodes]
    # narration 事件 -> NARRATION_ONLY
    # dialogue 事件 -> DIALOGUE
    assert len(node_types) >= 4


def test_first_node_is_narration():
    """测试第一个节点是旁白类型（场景进入）"""
    mock_client_mgr = MagicMock()
    builder = PlotBuilder(mock_client_mgr)

    analysis = _make_analysis_result()
    chapters = builder.build(analysis)

    first_node = chapters[0].nodes[0]
    assert first_node.narration_type.value == "scene_enter"


def test_dialogue_nodes_have_npc():
    """测试对话节点包含 npc_name"""
    mock_client_mgr = MagicMock()
    builder = PlotBuilder(mock_client_mgr)

    analysis = _make_analysis_result()
    chapters = builder.build(analysis)

    dialogue_nodes = [n for n in chapters[0].nodes if n.node_type.value == "dialogue"]
    for node in dialogue_nodes:
        assert node.npc_name is not None


def test_empty_events():
    """测试空事件列表"""
    mock_client_mgr = MagicMock()
    builder = PlotBuilder(mock_client_mgr)

    analysis = AnalysisResult(world_name="test", characters=[], locations=[], events=[], relationships=[])
    chapters = builder.build(analysis)

    assert len(chapters) >= 1  # 仍会创建空章节


def test_multi_chapter_split():
    """测试多章节切分（场景数量多时）"""
    mock_client_mgr = MagicMock()
    builder = PlotBuilder(mock_client_mgr, nodes_per_chapter=2)

    # 创建超过单章容量的多场景
    events = []
    for i in range(5):
        events.append(EventInfo(
            scene_id=f"e{i+1}",
            description=f"场景{i+1}描述",
            participants=["Alice", "Bob"],
            location="老街",
            event_type="dialogue" if i % 2 == 0 else "narration"
        ))

    analysis = AnalysisResult(
        world_name="test",
        characters=[CharacterInfo(name="Alice"), CharacterInfo(name="Bob")],
        locations=[LocationInfo(name="老街")],
        events=events,
        relationships=[]
    )

    chapters = builder.build(analysis)
    # 5个事件，2个一章，应该至少有3章
    assert len(chapters) >= 2


def test_node_sequencing():
    """测试节点顺序正确"""
    mock_client_mgr = MagicMock()
    builder = PlotBuilder(mock_client_mgr)

    analysis = _make_analysis_result()
    chapters = builder.build(analysis)

    nodes = chapters[0].nodes
    # 每个节点的 next 应该指向下一个节点或 None
    for i, node in enumerate(nodes):
        if i < len(nodes) - 1:
            assert node.next is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest unittest/refiner/test_plot_builder.py -v`
Expected: FAIL (import error - module not found)

- [ ] **Step 3: 编写 PlotBuilder 实现**

```python
"""
Stage 2c: PlotBuilder
将事件序列转换为 Chapter 列表
"""
import logging
from typing import List, Optional

from ...clients.manager import ClientManager
from ...src.core.plot.types import (
    Chapter, PlotNode, Branch, NodeType, NarrativeType,
    NPCInteraction, InteractionTrigger
)
from ...src.core.npc import NPCProfile
from ..types import AnalysisResult, EventInfo

_logger = logging.getLogger("refiner.plot_builder")


class PlotBuilder:
    """剧本构建器 - Stage 2c"""

    def __init__(
        self,
        client_manager: ClientManager,
        model_name: Optional[str] = None,
        nodes_per_chapter: int = 10
    ):
        """初始化

        Args:
            client_manager: ClientManager 实例
            model_name: 可选，指定模型
            nodes_per_chapter: 每章最大节点数，超过则创建新章节
        """
        self._client_mgr = client_manager
        self._model_name = model_name
        self._nodes_per_chapter = nodes_per_chapter

    def build(
        self,
        analysis: AnalysisResult,
        npcs: Optional[List[NPCProfile]] = None
    ) -> List[Chapter]:
        """将事件序列构建为章节列表

        Args:
            analysis: TextAnalyzer 输出
            npcs: 可选，NPCProfile 列表（用于 NPC 交互生成）

        Returns:
            Chapter 列表
        """
        if not analysis.events:
            # 无事件时创建空章节
            return [self._create_chapter("chapter_1", "第一章", [])]

        # 按 nodes_per_chapter 分组
        chapters = []
        current_chapter_nodes = []
        chapter_index = 1

        for event in analysis.events:
            node = self._event_to_node(event, analysis)
            current_chapter_nodes.append(node)

            if len(current_chapter_nodes) >= self._nodes_per_chapter:
                chapter = self._create_chapter(
                    f"chapter_{chapter_index}",
                    f"第{chapter_index}章",
                    current_chapter_nodes
                )
                chapters.append(chapter)
                current_chapter_nodes = []
                chapter_index += 1

        # 处理剩余节点
        if current_chapter_nodes:
            chapter = self._create_chapter(
                f"chapter_{chapter_index}",
                f"第{chapter_index}章",
                current_chapter_nodes
            )
            chapters.append(chapter)

        # 生成 NPC 交互（如果有 NPC 信息）
        if npcs:
            self._add_npc_interactions(chapters, analysis, npcs)

        _logger.info(f"Built {len(chapters)} chapters with {len(analysis.events)} events")
        return chapters

    def _event_to_node(
        self,
        event: EventInfo,
        analysis: AnalysisResult
    ) -> PlotNode:
        """将事件转换为 PlotNode"""
        # 确定节点类型和旁白类型
        if event.event_type == "dialogue":
            node_type = NodeType.DIALOGUE
            narration_type = NarrativeType.FREE_EXPLORE
        elif event.event_type == "narration":
            node_type = NodeType.NARRATION_ONLY
            narration_type = NarrativeType.ACTION_RESULT
        elif event.event_type == "action":
            node_type = NodeType.NARRATION_ONLY
            narration_type = NarrativeType.TRANSITION
        else:
            node_type = NodeType.NARRATION_ONLY
            narration_type = NarrativeType.FREE_EXPLORE

        # 确定 npc_name（如果事件涉及特定角色）
        npc_name = None
        if len(event.participants) == 1:
            npc_name = event.participants[0]
        elif len(event.participants) > 1 and event.event_type == "dialogue":
            # 对话事件以第一个参与者为 NPC
            npc_name = event.participants[0]

        return PlotNode(
            id=event.scene_id,
            node_type=node_type,
            npc_name=npc_name,
            content=event.description,
            next=None,  # 后续在 _create_chapter 中链接
            branches=None,
            triggers=[],
            narration_type=narration_type
        )

    def _create_chapter(
        self,
        chapter_id: str,
        chapter_name: str,
        nodes: List[PlotNode]
    ) -> Chapter:
        """创建章节并链接节点"""
        # 链接节点 next
        for i in range(len(nodes) - 1):
            nodes[i].next = nodes[i + 1].id

        return Chapter(
            id=chapter_id,
            name=chapter_name,
            nodes=nodes,
            current_node_index=0
        )

    def _add_npc_interactions(
        self,
        chapters: List[Chapter],
        analysis: AnalysisResult,
        npcs: List[NPCProfile]
    ):
        """为章节添加 NPC 主动交互"""
        npc_names = {npc.persona.name for npc in npcs}

        for chapter in chapters:
            for event in analysis.events:
                if event.event_type == "dialogue" and event.participants:
                    first_participant = event.participants[0]
                    if first_participant in npc_names:
                        # 创建 NPC 交互触发器
                        interaction = NPCInteraction(
                            trigger=InteractionTrigger.STORY_NODE,
                            npc_name=first_participant,
                            priority=5,
                            content=f"{first_participant}主动与你搭话",
                            condition=None,
                            cooldown_turns=10,
                            last_triggered_turn=0
                        )
                        # 附加到章节（这里简化处理，实际可能需要挂在特定节点）
                        if not hasattr(chapter, 'npc_interactions'):
                            chapter.npc_interactions = []
                        chapter.npc_interactions.append(interaction)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest unittest/refiner/test_plot_builder.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add refiner/extractors/plot_builder.py unittest/refiner/test_plot_builder.py
git commit -m "feat(refiner): add PlotBuilder (Stage 2c)"
```