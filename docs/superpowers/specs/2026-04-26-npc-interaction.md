# NPCInteractionManager 模块设计

## 1. 职责

管理 NPC 主动发起交互的混合触发机制。检测并队列化三种触发类型的事件：
- **剧情节点触发**（STORY_NODE）：特定主线进度时 NPC 自动出现
- **环境感知触发**（LOCATION_CHANGE）：玩家进入某区域时相关 NPC 主动搭话
- **关系驱动触发**（RELATION_THRESHOLD）：NPC 与玩家关系达到某阈值后主动关心/互动

## 2. 核心数据结构

```python
class InteractionTrigger(Enum):
    STORY_NODE          # 剧情节点触发
    LOCATION_CHANGE     # 环境感知触发
    RELATION_THRESHOLD  # 关系阈值触发

@dataclass
class NPCInteraction:
    trigger: InteractionTrigger
    npc_name: str
    priority: int                    # 优先级，数值越高越优先
    content: Optional[str]           # 预定义的交互内容
    condition: Optional[Condition]  # 条件（用于动态判断）
    cooldown_turns: int              # 触发后多少回合不能再次触发
    last_triggered_turn: int = 0     # 上次触发时的对话轮次

@dataclass
class InteractionQueue:
    """NPC交互事件队列"""
    queue: List[NPCInteraction]
    current_interaction: Optional[NPCInteraction] = None

@dataclass
class PlotContext:
    """传递给触发器检查的上下文"""
    current_chapter: str
    current_node: str
    current_location: str
    conversation_turns: int
    relationship_states: Dict[str, int]  # npc_name -> relationship_value
```

## 3. 主要方法

```python
class NPCInteractionManager:
    def __init__(
        self,
        asset_manager: AssetManager,
        plot_manager: StoryPlotManager
    ):
        self._asset = asset_manager
        self._plot = plot_manager

    def check_and_queue_interactions(
        self,
        context: PlotContext
    ) -> InteractionQueue:
        """检查所有触发条件，返回待执行的交互队列"""

    def register_interaction(
        self,
        trigger: InteractionTrigger,
        npc_name: str,
        priority: int = 5,
        content: Optional[str] = None,
        cooldown_turns: int = 10
    ) -> None:
        """注册新的NPC交互事件"""

    def get_next_interaction(self) -> Optional[NPCInteraction]:
        """获取队列中下一个待执行的交互"""

    def mark_interaction_done(self, npc_name: str) -> None:
        """标记某NPC的交互已完成（进入冷却）"""
```

## 4. 触发条件检测

### 4.1 STORY_NODE（剧情节点触发）

从章节配置的 PlotNode 中读取，StoryPlotManager 在节点为 NPC_INTERACT 类型时直接触发：

```yaml
- id: "n_special"
  node_type: "NPC_INTERACT"
  npc_name: "alice"
  content: "Alice突然出现在你面前"
  triggers:
    - type: "STORY_NODE"
      condition: null  # 到达此节点即触发
      event: "alice_appears"
```

### 4.2 LOCATION_CHANGE（环境感知触发）

```python
def check_location_triggers(context: PlotContext) -> List[NPCInteraction]:
    """检查地点触发器"""
    interactions = []

    # 从世界模型获取当前地点的关联NPC
    current_world = self._asset.get_current_world()
    location_npcs = current_world.get_npcs_at_location(context.current_location)

    for npc_name in location_npcs:
        # 检查该NPC是否有"进入地点"触发器
        trigger = self._location_triggers.get((context.current_location, npc_name))
        if trigger and self._check_cooldown(trigger, context.conversation_turns):
            interactions.append(trigger)

    return interactions
```

配置格式：
```yaml
# assets/npc/alice/triggers.yaml
location_triggers:
  coffee_shop:
    condition: null  # 无条件触发
    priority: 5
    content: "Alice正在咖啡馆喝咖啡，看到你进来向你招手"
    cooldown_turns: 10

  library:
    condition:
      relationship_min: 20  # 关系值>=20才触发
    priority: 3
    content: null  # 使用NPC默认搭话
    cooldown_turns: 5
```

### 4.3 RELATION_THRESHOLD（关系驱动触发）

```python
def check_relation_triggers(context: PlotContext) -> List[NPCInteraction]:
    """检查关系阈值触发器"""
    interactions = []

    for npc_name, relationship in context.relationship_states.items():
        trigger = self._relation_triggers.get(npc_name)
        if not trigger:
            continue

        # 检查是否满足关系阈值
        if relationship >= trigger.condition.get("relationship_min", 0):
            if self._check_cooldown(trigger, context.conversation_turns):
                interactions.append(trigger)

    return interactions
```

配置格式：
```yaml
# assets/npc/alice/triggers.yaml
relation_triggers:
  - condition:
      relationship_min: 30
    priority: 7
    content: "Alice似乎有些话想对你说..."
    cooldown_turns: 15
```

## 5. 优先级与队列

```python
# 优先级排序
QUEUE_PRIORITY = {
    InteractionTrigger.STORY_NODE: 10,      # 最高，剧情优先
    InteractionTrigger.LOCATION_CHANGE: 5,
    InteractionTrigger.RELATION_THRESHOLD: 3  # 最低
}

def check_and_queue_interactions(self, context: PlotContext) -> InteractionQueue:
    all_interactions = []

    # 收集所有触发
    all_interactions.extend(self._get_story_node_triggers(context))
    all_interactions.extend(self.check_location_triggers(context))
    all_interactions.extend(self.check_relation_triggers(context))

    # 按优先级排序
    all_interactions.sort(key=lambda x: x.priority, reverse=True)

    queue = InteractionQueue(queue=all_interactions)
    return queue
```

## 6. 与其他模块的配合

### 6.1 与 StoryPlotManager 配合

```python
# StoryPlotManager 在advance_to时通知
class StoryPlotManager:
    def advance_to(self, node_id):
        node = self.get_node(node_id)
        if node.node_type == NodeType.NPC_INTERACT:
            npc_manager.register_interaction(
                trigger=InteractionTrigger.STORY_NODE,
                npc_name=node.npc_name,
                content=node.content,
                priority=10  # 剧情节点最高优先
            )
```

### 6.2 与 GameLoopController 配合

```python
class GameLoopController:
    def on_turn_end(self, session):
        context = PlotContext(
            current_chapter=session.plot_state.chapter_id,
            current_node=session.plot_state.node_id,
            current_location=session.current_location,
            conversation_turns=session.turn_count,
            relationship_states=session.npc_relationships
        )

        queue = npc_manager.check_and_queue_interactions(context)

        if queue.has_interaction():
            session.npc_interaction_queue = queue
            # 下一轮优先处理NPC交互
```

### 6.3 与 NarratorGenerator 配合

```python
# NPC主动交互时，先生成旁白描述NPC出现
def execute_npc_interaction(interaction: NPCInteraction):
    if interaction.content:
        # 使用预定义内容
        narrative = interaction.content
    else:
        # 让NarratorGenerator生成
        narrative = narrator.generate(
            NarrativeContext.SCENE_ENTER,
            location=session.current_location,
            npc_name=interaction.npc_name
        )

    # NPC发言
    npc_response = engine.chat(
        f"[{interaction.npc_name}] 自动触发对话",
        session_id=session.session_id
    )
```

### 6.4 与 OptionGenerator 配合

```python
# NPC主动交互后，如果NPC提出邀请，需要生成选项
if npc_response.get("suggestion"):
    options = option_generator.generate_npc_suggestion_options(
        npc_response["suggestion"]["type"]
    )
    session.option_pending = options
```

## 7. Session 持久化扩展

```python
# ConversationSession 中新增
class ConversationSession:
    npc_interaction_queue: List[NPCInteraction]
    active_npc_interaction: Optional[NPCInteraction]
    npc_relationships: Dict[str, int]  # NPC好感度等关系值
```

## 8. NPC发言格式

NPC主动交互的输出格式：

```
[旁白（可选）]
{narrative}

[{NPC名称}]
{npc_dialogue}

{选项（如果有）}
1. [接受]
2. [拒绝]
3. [自由输入]
```

## 9. 冷却机制

```python
def _check_cooldown(self, trigger: NPCInteraction, current_turn: int) -> bool:
    if trigger.last_triggered_turn == 0:
        return True
    return (current_turn - trigger.last_triggered_turn) >= trigger.cooldown_turns
```

## 10. 配置扩展

在 `config/settings.yaml` 中增加：

```yaml
npc_interaction:
  enable_npc_initiative: true
  max_queue_size: 3
  default_cooldown_turns: 10
  location_trigger_radius: 1  # 地点触发范围（临近地点也算）
```
