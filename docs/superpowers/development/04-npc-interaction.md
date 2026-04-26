# NPCInteractionManager 开发指南

## 依赖关系

- **前置**: AssetManager、StoryPlotManager
- **后续**: 被 GameLoopController 调用
- **配合**: StoryPlotManager（触发器）、NarratorGenerator（NPC出场旁白）

## 核心概念

NPC主动交互采用混合触发：剧情节点、环境感知、关系阈值。触发后进入队列，优先级排序后依次执行。

## 文件: src/core/plot/npc_interaction.py

```python
"""
NPCInteractionManager - NPC主动交互管理
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict

from .types import InteractionTrigger, NPCInteraction, TriggerType, Trigger, Condition, PlotContext
from ..asset_manager import AssetManager
from ...utils.logger import get_logger

_logger = get_logger("rubsgame.npc_interaction")


QUEUE_PRIORITY = {
    InteractionTrigger.STORY_NODE: 10,
    InteractionTrigger.LOCATION_CHANGE: 5,
    InteractionTrigger.RELATION_THRESHOLD: 3
}


@dataclass
class InteractionQueue:
    """NPC交互事件队列"""
    interactions: List[NPCInteraction] = field(default_factory=list)

    def is_empty(self) -> bool:
        return len(self.interactions) == 0

    def pop(self) -> Optional[NPCInteraction]:
        """取出最高优先级的交互"""
        if not self.interactions:
            return None
        self.interactions.sort(key=lambda x: x.priority, reverse=True)
        return self.interactions.pop(0)

    def peek(self) -> Optional[NPCInteraction]:
        """查看最高优先级交互但不取出"""
        if not self.interactions:
            return None
        sorted_list = sorted(self.interactions, key=lambda x: x.priority, reverse=True)
        return sorted_list[0]


class NPCInteractionManager:
    """管理NPC主动发起的交互"""

    def __init__(
        self,
        asset_manager: AssetManager,
        plot_manager,  # StoryPlotManager
        default_cooldown: int = 10
    ):
        self._asset = asset_manager
        self._plot = plot_manager
        self._default_cooldown = default_cooldown

        # 触发器注册表
        self._story_triggers: Dict[str, List[NPCInteraction]] = {}  # node_id -> triggers
        self._location_triggers: Dict[str, List[NPCInteraction]] = {}  # location -> triggers
        self._relation_triggers: Dict[str, List[NPCInteraction]] = {}  # npc_name -> triggers

        # 冷却记录
        self._cooldown_records: Dict[str, int] = {}  # npc_name -> last_triggered_turn

    def register_story_trigger(
        self,
        node_id: str,
        npc_name: str,
        content: Optional[str] = None,
        priority: int = 10
    ) -> None:
        """注册剧情节点触发的NPC交互"""
        interaction = NPCInteraction(
            trigger=InteractionTrigger.STORY_NODE,
            npc_name=npc_name,
            priority=priority,
            content=content,
            cooldown_turns=self._default_cooldown
        )
        if node_id not in self._story_triggers:
            self._story_triggers[node_id] = []
        self._story_triggers[node_id].append(interaction)

    def register_location_trigger(
        self,
        location: str,
        npc_name: str,
        condition: Optional[Condition] = None,
        content: Optional[str] = None,
        priority: int = 5,
        cooldown_turns: Optional[int] = None
    ) -> None:
        """注册地点触发的NPC交互"""
        interaction = NPCInteraction(
            trigger=InteractionTrigger.LOCATION_CHANGE,
            npc_name=npc_name,
            priority=priority,
            content=content,
            condition=condition,
            cooldown_turns=cooldown_turns or self._default_cooldown
        )
        if location not in self._location_triggers:
            self._location_triggers[location] = []
        self._location_triggers[location].append(interaction)
        _logger.debug(f"Registered location trigger: {npc_name} @ {location}")

    def register_relation_trigger(
        self,
        npc_name: str,
        condition: Condition,
        content: Optional[str] = None,
        priority: int = 3,
        cooldown_turns: Optional[int] = None
    ) -> None:
        """注册关系触发的NPC交互"""
        interaction = NPCInteraction(
            trigger=InteractionTrigger.RELATION_THRESHOLD,
            npc_name=npc_name,
            priority=priority,
            content=content,
            condition=condition,
            cooldown_turns=cooldown_turns or self._default_cooldown
        )
        if npc_name not in self._relation_triggers:
            self._relation_triggers[npc_name] = []
        self._relation_triggers[npc_name].append(interaction)
        _logger.debug(f"Registered relation trigger for: {npc_name}")

    def check_and_queue_interactions(self, context: PlotContext) -> InteractionQueue:
        """检查所有触发条件，返回待执行的交互队列"""
        queue = InteractionQueue()

        # 1. 检查剧情节点触发器
        if context.current_node in self._story_triggers:
            for trigger in self._story_triggers[context.current_node]:
                if self._check_cooldown(trigger, context.conversation_turns):
                    queue.interactions.append(trigger)

        # 2. 检查地点触发器
        if context.current_location in self._location_triggers:
            for trigger in self._location_triggers[context.current_location]:
                if self._check_cooldown(trigger, context.conversation_turns):
                    if self._check_condition(trigger, context):
                        queue.interactions.append(trigger)

        # 3. 检查关系触发器
        for npc_name, relationship in context.relationship_states.items():
            if npc_name in self._relation_triggers:
                for trigger in self._relation_triggers[npc_name]:
                    if self._check_cooldown(trigger, context.conversation_turns):
                        if self._check_condition(trigger, context, relationship):
                            queue.interactions.append(trigger)

        _logger.debug(f"Found {len(queue.interactions)} potential NPC interactions")
        return queue

    def mark_interaction_done(self, npc_name: str, current_turn: int) -> None:
        """标记某NPC的交互已完成（进入冷却）"""
        self._cooldown_records[npc_name] = current_turn
        _logger.debug(f"NPC {npc_name} interaction marked done, cooldown until turn {current_turn + self._default_cooldown}")

    def get_next_interaction(self, queue: InteractionQueue) -> Optional[NPCInteraction]:
        """获取队列中下一个待执行的交互"""
        return queue.pop()

    def _check_cooldown(self, trigger: NPCInteraction, current_turn: int) -> bool:
        """检查是否在冷却中"""
        last_turn = self._cooldown_records.get(trigger.npc_name, 0)
        return (current_turn - last_turn) >= trigger.cooldown_turns

    def _check_condition(
        self,
        trigger: NPCInteraction,
        context: PlotContext,
        relationship: Optional[int] = None
    ) -> bool:
        """检查触发器条件"""
        if not trigger.condition:
            return True

        cond = trigger.condition

        # 关系条件
        if relationship is not None:
            if cond.relationship_min is not None and relationship < cond.relationship_min:
                return False
            if cond.relationship_max is not None and relationship > cond.relationship_max:
                return False

        # TODO: 支持更多条件类型
        return True
```

## NPCInteraction 数据结构

```python
@dataclass
class NPCInteraction:
    trigger: InteractionTrigger
    npc_name: str
    priority: int = 5
    content: Optional[str] = None
    condition: Optional[Condition] = None
    cooldown_turns: int = 10
    last_triggered_turn: int = 0
```

## 与其他模块配合

### 与 StoryPlotManager 配合

```python
# StoryPlotManager 在节点为 NPC_INTERACT 时调用
class StoryPlotManager:
    def advance_to(self, node_id: str) -> PlotNode:
        node = self._find_node(node_id)
        if node and node.node_type == NodeType.NPC_INTERACT:
            self._npc_manager.register_story_trigger(
                node_id=node_id,
                npc_name=node.npc_name,
                content=node.content,
                priority=10
            )
        # ... 其余逻辑
```

### 与 GameLoopController 配合

```python
# GameLoopController 每轮结束后检查
class GameLoopController:
    def on_turn_end(self, session):
        context = PlotContext(
            current_chapter=session.plot_state.chapter_id,
            current_node=session.plot_state.node_id,
            current_location=session.current_location,
            conversation_turns=session.turn_count,
            relationship_states=session.npc_relationships
        )

        queue = self._npc_manager.check_and_queue_interactions(context)

        if not queue.is_empty():
            session.npc_interaction_queue = queue
            # 下一轮优先处理NPC交互

    def process_npc_interaction(self, session):
        """处理队列中的NPC交互"""
        if not session.npc_interaction_queue:
            return None

        interaction = self._npc_manager.get_next_interaction(session.npc_interaction_queue)
        if not interaction:
            return None

        # 生成NPC出场旁白（如果有）
        narrative = None
        if interaction.content:
            narrative = interaction.content
        else:
            narrative = self._narrator.generate(
                context=NarrativeContext.SCENE_ENTER,
                location=session.current_location,
                npc_name=interaction.npc_name
            )

        # 标记冷却
        self._npc_manager.mark_interaction_done(
            interaction.npc_name,
            session.turn_count
        )

        session.active_npc_interaction = interaction

        return {
            "narrative": narrative,
            "npc_name": interaction.npc_name,
            "trigger": interaction.trigger.value
        }
```

## 触发器配置示例

在 NPC 资源目录下创建 `triggers.yaml`：

```yaml
# assets/npc/alice/triggers.yaml
location_triggers:
  coffee_shop:
    condition: null
    priority: 5
    content: "Alice正在咖啡馆喝咖啡，看到你进来向你招手"
    cooldown_turns: 10

  library:
    condition:
      relationship_min: 20
    priority: 3
    content: null
    cooldown_turns: 5

relation_triggers:
  - condition:
      relationship_min: 30
    priority: 7
    content: "Alice似乎有些话想对你说..."
    cooldown_turns: 15
```

## Session 扩展

```python
# ConversationSession 中新增
class ConversationSession:
    # ... 现有字段 ...

    npc_interaction_queue: List[NPCInteraction] = []  # NPC交互事件队列
    active_npc_interaction: Optional[NPCInteraction] = None  # 当前执行的NPC交互
    npc_relationships: Dict[str, int] = {}  # NPC好感度等关系值
```

## 测试用例骨架

```python
# unittest/core/plot/test_npc_interaction.py
import pytest
from unittest.mock import Mock
from src.core.plot.npc_interaction import (
    NPCInteractionManager, InteractionQueue, NPCInteraction, InteractionTrigger
)
from src.core.plot.types import TriggerType, Condition, PlotContext


class TestNPCInteractionManager:
    @pytest.fixture
    def mock_asset_manager(self):
        return Mock()

    @pytest.fixture
    def mock_plot_manager(self):
        return Mock()

    def test_register_and_check_location_trigger(self, mock_asset_manager, mock_plot_manager):
        manager = NPCInteractionManager(mock_asset_manager, mock_plot_manager)

        manager.register_location_trigger(
            location="咖啡馆",
            npc_name="alice",
            content="Alice在咖啡馆等你",
            priority=5
        )

        context = PlotContext(
            current_chapter="chapter_01",
            current_node="n1",
            current_location="咖啡馆",
            conversation_turns=0,
            relationship_states={}
        )

        queue = manager.check_and_queue_interactions(context)
        assert not queue.is_empty()
        assert queue.peek().npc_name == "alice"

    def test_cooldown_mechanism(self, mock_asset_manager, mock_plot_manager):
        manager = NPCInteractionManager(mock_asset_manager, mock_plot_manager, default_cooldown=5)

        manager.register_location_trigger(
            location="咖啡馆",
            npc_name="alice",
            content="Alice在咖啡馆"
        )

        context = PlotContext(
            current_chapter="chapter_01",
            current_node="n1",
            current_location="咖啡馆",
            conversation_turns=0,
            relationship_states={}
        )

        queue1 = manager.check_and_queue_interactions(context)
        assert not queue1.is_empty()

        # 标记完成
        manager.mark_interaction_done("alice", 0)

        # 还在冷却中
        queue2 = manager.check_and_queue_interactions(context)
        # 应该为空或不在队列中

    def test_priority_ordering(self, mock_asset_manager, mock_plot_manager):
        manager = NPCInteractionManager(mock_asset_manager, mock_plot_manager)

        manager.register_story_trigger("n1", "alice", "Alice story", priority=10)
        manager.register_location_trigger("咖啡馆", "bob", "Bob location", priority=5)

        context = PlotContext(
            current_chapter="chapter_01",
            current_node="n1",
            current_location="咖啡馆",
            conversation_turns=0,
            relationship_states={}
        )

        queue = manager.check_and_queue_interactions(context)
        first = queue.pop()
        assert first.npc_name == "alice"  # story trigger 优先级更高
```

## 配置项

在 `config/settings.yaml` 中增加：

```yaml
npc_interaction:
  enable_npc_initiative: true
  max_queue_size: 3
  default_cooldown_turns: 10
```
