# StoryPlotManager 开发指南

## 依赖关系

- **前置**: types.py（定义数据结构）、plot_loader.py（YAML 加载）
- **后续**: 被 narrator.py、option_generator.py、npc_interaction.py、game_loop.py 调用

## 文件: src/core/plot/types.py

定义所有共用数据类型。

```python
"""
剧情系统共用数据类型
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any


class NodeType(Enum):
    """节点类型"""
    DIALOGUE = "dialogue"           # 对话节点
    CHOICE = "choice"               # 分支选择节点
    NARRATION_ONLY = "narration_only"  # 仅旁白节点
    BRANCH = "branch"               # 多分支节点
    NPC_INTERACT = "npc_interact"   # NPC主动交互节点


class TriggerType(Enum):
    """触发器类型"""
    STORY_PROGRESS = "story_progress"
    LOCATION_CHANGE = "location_change"
    RELATION_THRESHOLD = "relation_threshold"


class NarrativeType(Enum):
    """旁白类型"""
    SCENE_ENTER = "scene_enter"
    SCENE_EXIT = "scene_exit"
    EMOTION_BUILD = "emotion_build"
    TRANSITION = "transition"
    ACTION_RESULT = "action_result"
    CHAPTER_START = "chapter_start"
    CHAPTER_END = "chapter_end"
    FREE_EXPLORE = "free_explore"


@dataclass
class Condition:
    """分支/触发器条件"""
    relationship_min: Optional[int] = None
    relationship_max: Optional[int] = None
    has_item: Optional[str] = None
    flag: Optional[str] = None


@dataclass
class Branch:
    """分支选项"""
    id: str
    label: str
    condition: Optional[Condition] = None
    next_node: str = ""


@dataclass
class Trigger:
    """事件触发器"""
    type: TriggerType
    condition: Optional[Condition] = None
    event: str = ""


@dataclass
class PlotNode:
    """剧情节点"""
    id: str
    node_type: NodeType = NodeType.DIALOGUE
    npc_name: Optional[str] = None
    content: str = ""
    next: Optional[str] = None
    branches: List[Branch] = field(default_factory=list)
    triggers: List[Trigger] = field(default_factory=list)
    narration_type: Optional[NarrativeType] = None


@dataclass
class Chapter:
    """章节"""
    id: str
    name: str
    nodes: List[PlotNode] = field(default_factory=list)
    current_node_index: int = 0


@dataclass
class PlotState:
    """当前剧情状态（持久化用）"""
    chapter_id: str = ""
    node_id: str = ""
    is_exploring: bool = True
    is_branch_point: bool = False
    queued_narrative: Optional[str] = None


@dataclass
class PlotContext:
    """传递给触发器检查的上下文"""
    current_chapter: str
    current_node: str
    current_location: str
    conversation_turns: int
    relationship_states: Dict[str, int] = field(default_factory=dict)
```

## 文件: src/core/plot/plot_loader.py

加载章节配置。

```python
"""
章节配置加载器
"""
import yaml
from pathlib import Path
from typing import Optional

from .types import Chapter, PlotNode, Branch, Trigger, Condition, NodeType, TriggerType, NarrativeType
from ...utils.logger import get_logger

_logger = get_logger("rubsgame.plot_loader")


class PlotLoader:
    """从 YAML 加载章节配置"""

    def __init__(self, plot_dir: str):
        self._plot_dir = Path(plot_dir)

    def load(self, chapter_id: str) -> Chapter:
        """加载章节"""
        chapter_path = self._plot_dir / chapter_id / "chapter.yaml"
        if not chapter_path.exists():
            raise FileNotFoundError(f"Chapter not found: {chapter_path}")

        with open(chapter_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return self._parse_chapter(data["chapter"])

    def _parse_chapter(self, data: dict) -> Chapter:
        nodes = [self._parse_node(n) for n in data.get("nodes", [])]
        return Chapter(
            id=data["id"],
            name=data["name"],
            nodes=nodes
        )

    def _parse_node(self, data: dict) -> PlotNode:
        node_type = NodeType(data.get("node_type", "dialogue"))
        narration_str = data.get("narration_type")
        narration_type = NarrativeType(narration_str) if narration_str else None

        branches = [self._parse_branch(b) for b in data.get("branches", [])]
        triggers = [self._parse_trigger(t) for t in data.get("triggers", [])]

        return PlotNode(
            id=data["id"],
            node_type=node_type,
            npc_name=data.get("npc_name"),
            content=data.get("content", ""),
            next=data.get("next"),
            branches=branches,
            triggers=triggers,
            narration_type=narration_type
        )

    def _parse_branch(self, data: dict) -> Branch:
        cond_data = data.get("condition")
        condition = self._parse_condition(cond_data) if cond_data else None
        return Branch(
            id=data["id"],
            label=data["label"],
            condition=condition,
            next_node=data["next_node"]
        )

    def _parse_trigger(self, data: dict) -> Trigger:
        cond_data = data.get("condition")
        condition = self._parse_condition(cond_data) if cond_data else None
        return Trigger(
            type=TriggerType(data["type"]),
            condition=condition,
            event=data.get("event", "")
        )

    def _parse_condition(self, data: dict) -> Condition:
        return Condition(
            relationship_min=data.get("relationship_min"),
            relationship_max=data.get("relationship_max"),
            has_item=data.get("has_item"),
            flag=data.get("flag")
        )
```

## 文件: src/core/plot/plot_manager.py

主模块实现。

```python
"""
StoryPlotManager - 主线进度管理
"""
from typing import List, Optional, Dict

from .types import Chapter, PlotNode, PlotState, PlotContext, NodeType, Branch, Trigger
from .plot_loader import PlotLoader
from ..asset_manager import AssetManager
from ...utils.logger import get_logger

_logger = get_logger("rubsgame.plot_manager")


class StoryPlotManager:
    """管理主线进度、章节状态和事件触发器"""

    def __init__(self, asset_manager: AssetManager, plot_dir: str):
        self._asset = asset_manager
        self._loader = PlotLoader(plot_dir)
        self._chapters: Dict[str, Chapter] = {}
        self._current_chapter: Optional[Chapter] = None
        self._state = PlotState(is_exploring=True)
        self._location_triggers: Dict[str, List[Trigger]] = {}
        self._relation_triggers: Dict[str, List[Trigger]] = {}

    # ==================== 章节加载 ====================

    def load_chapter(self, chapter_id: str) -> Chapter:
        """加载章节"""
        if chapter_id in self._chapters:
            chapter = self._chapters[chapter_id]
        else:
            chapter = self._loader.load(chapter_id)
            self._chapters[chapter_id] = chapter

        self._current_chapter = chapter
        self._state.chapter_id = chapter_id
        self._state.is_exploring = False

        _logger.info(f"Loaded chapter: {chapter_id}")
        return chapter

    def get_current_chapter(self) -> Optional[Chapter]:
        return self._current_chapter

    # ==================== 进度管理 ====================

    def get_current_state(self) -> PlotState:
        """返回当前剧情状态"""
        return self._state

    def get_current_node(self) -> Optional[PlotNode]:
        """获取当前节点"""
        if not self._current_chapter:
            return None
        for node in self._current_chapter.nodes:
            if node.id == self._state.node_id:
                return node
        return None

    def advance_to(self, node_id: str) -> PlotNode:
        """推进到指定节点"""
        if not self._current_chapter:
            raise RuntimeError("No chapter loaded")

        node = self._find_node(node_id)
        if not node:
            raise ValueError(f"Node not found: {node_id}")

        self._state.node_id = node_id
        self._state.is_branch_point = node.node_type == NodeType.BRANCH
        self._state.queued_narrative = None

        _logger.debug(f"Advanced to node: {node_id}")
        return node

    def make_choice(self, branch_id: str) -> PlotNode:
        """玩家选择分支后调用"""
        current = self.get_current_node()
        if not current or not current.branches:
            raise RuntimeError("Not at a branch point")

        for branch in current.branches:
            if branch.id == branch_id:
                return self.advance_to(branch.next_node)

        raise ValueError(f"Branch not found: {branch_id}")

    def get_available_choices(self) -> List[Branch]:
        """获取当前可用的分支选项"""
        current = self.get_current_node()
        if not current or current.node_type != NodeType.BRANCH:
            return []

        available = []
        for branch in current.branches:
            if self._check_branch_condition(branch):
                available.append(branch)
        return available

    def _find_node(self, node_id: str) -> Optional[PlotNode]:
        if not self._current_chapter:
            return None
        for node in self._current_chapter.nodes:
            if node.id == node_id:
                return node
        return None

    def _check_branch_condition(self, branch: Branch) -> bool:
        """检查分支条件是否满足"""
        if not branch.condition:
            return True
        # TODO: 实现条件检查逻辑
        return True

    # ==================== 探索模式 ====================

    def is_exploring(self) -> bool:
        """当前是否在自由探索模式"""
        return self._state.is_exploring

    def get_available_locations(self) -> List[str]:
        """获取玩家可前往的地点列表"""
        world = self._asset.get_current_world()
        if not world:
            return []
        return [loc.name for loc in world.locations]

    def move_to_location(self, location_name: str) -> bool:
        """玩家前往某地点"""
        world = self._asset.get_current_world()
        if not world:
            return False

        for loc in world.locations:
            if loc.name == location_name:
                _logger.debug(f"Player moved to: {location_name}")
                return True

        _logger.warning(f"Location not found: {location_name}")
        return False

    # ==================== 触发器 ====================

    def check_triggers(self, context: PlotContext) -> List[Trigger]:
        """检查所有触发器"""
        triggers = []

        # 检查剧情节点触发器
        current = self.get_current_node()
        if current:
            triggers.extend(current.triggers)

        # 检查地点触发器
        location_key = context.current_location
        if location_key in self._location_triggers:
            triggers.extend(self._location_triggers[location_key])

        # 检查关系触发器
        for npc_name, relationship in context.relationship_states.items():
            if npc_name in self._relation_triggers:
                for trigger in self._relation_triggers[npc_name]:
                    if self._check_trigger_condition(trigger, relationship):
                        triggers.append(trigger)

        return triggers

    def register_trigger(self, trigger: Trigger, npc_name: Optional[str] = None) -> None:
        """注册触发器"""
        if trigger.type == TriggerType.LOCATION_CHANGE:
            if not self._location_triggers.get(trigger.event):
                self._location_triggers[trigger.event] = []
            self._location_triggers[trigger.event].append(trigger)
        elif trigger.type == TriggerType.RELATION_THRESHOLD and npc_name:
            if not self._relation_triggers.get(npc_name):
                self._relation_triggers[npc_name] = []
            self._relation_triggers[npc_name].append(trigger)

    def _check_trigger_condition(self, trigger: Trigger, relationship: int) -> bool:
        """检查触发器条件"""
        if not trigger.condition:
            return True
        cond = trigger.condition
        if cond.relationship_min and relationship < cond.relationship_min:
            return False
        if cond.relationship_max and relationship > cond.relationship_max:
            return False
        return True
```

## 测试用例骨架

```python
# unittest/core/plot/test_plot_manager.py
import pytest
from src.core.plot.plot_manager import StoryPlotManager
from src.core.plot.types import Chapter, PlotNode, NodeType, PlotState


class TestStoryPlotManager:
    def test_load_chapter(self, tmp_path):
        # 创建临时章节配置
        chapter_dir = tmp_path / "chapter_01"
        chapter_dir.mkdir()
        (chapter_dir / "chapter.yaml").write_text("""
chapter:
  id: "chapter_01"
  name: "测试章节"
  nodes:
    - id: "n1"
      node_type: "NARRATION_ONLY"
      content: "测试内容"
""")
        # TODO: 实现测试
        pass

    def test_advance_to_node(self):
        # TODO: 实现测试
        pass

    def test_is_exploring(self):
        # TODO: 实现测试
        pass
```

## 配置项

在 `config/settings.yaml` 中增加：

```yaml
visual_novel:
  chapters_dir: "assets/plot/"
  default_chapter: "chapter_01"
```
