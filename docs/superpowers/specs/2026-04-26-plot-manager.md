# StoryPlotManager 模块设计

## 1. 职责

管理主线进度、章节状态和事件触发器队列。判断当前剧情状态（自由探索 / 章节节点 / 分支点），决定何时推进剧情、何时开放选项。

## 2. 核心数据结构

```python
@dataclass
class Chapter:
    id: str                           # 章节唯一标识
    name: str                         # 章节名称
    nodes: List[PlotNode]             # 章节内的剧情节点顺序列表
    current_node_index: int = 0       # 当前到达的节点索引

@dataclass
class PlotNode:
    id: str                           # 节点唯一标识
    node_type: NodeType               # 节点类型
    npc_name: Optional[str]            # 指定发言NPC，None则由系统决定
    content: str                      # 节点内容模板
    next: Optional[str]               # 单线下一节点ID
    branches: Optional[List[Branch]]  # 分支列表（多选一）
    triggers: List[Trigger]           # 触发条件列表
    narration_type: NarrativeType     # 此节点希望的旁白类型

@dataclass
class Branch:
    id: str                           # 分支ID
    label: str                        # 显示给玩家的分支名
    condition: Optional[Condition]    # 满足条件才显示
    next_node: str                   # 跳转到的节点

@dataclass
class Trigger:
    type: TriggerType                 # 触发类型
    condition: Any                    # 触发条件
    event: str                       # 触发的事件ID

class NodeType(Enum):
    DIALOGUE        # 对话节点
    CHOICE          # 分支选择节点
    NARRATION_ONLY  # 仅旁白节点
    BRANCH          # 多分支节点
    NPC_INTERACT    # NPC主动交互节点

class TriggerType(Enum):
    STORY_PROGRESS     # 剧情进度触发
    LOCATION_CHANGE    # 地点变化触发
    RELATION_THRESHOLD # 关系阈值触发
```

## 3. 主要方法

### 3.1 进度管理

```python
class StoryPlotManager:
    def load_chapter(chapter_id: str) -> Chapter
        """从 assets/plot/{chapter_id}/ 加载章节配置"""

    def get_current_state() -> PlotState
        """返回当前剧情状态"""

    def advance_to(node_id: str) -> None
        """推进到指定节点"""

    def make_choice(branch_id: str) -> None
        """玩家选择分支后调用"""

    def get_available_choices() -> List[Branch]
        """获取当前可用的分支选项"""
```

### 3.2 触发器检查

```python
    def check_triggers(context: PlotContext) -> List[str]
        """检查所有触发器，返回待触发的事件ID列表"""

    def register_trigger(trigger: Trigger) -> None
        """注册新的触发器（用于动态剧情）"""
```

### 3.3 探索模式

```python
    def is_exploring() -> bool
        """当前是否在自由探索模式"""

    def get_available_locations() -> List[str]
        """获取玩家可前往的地点列表（来自WorldKnowledge）"""

    def move_to_location(location_name: str) -> bool
        """玩家前往某地点，返回是否触发新剧情"""
```

## 4. 与其他模块的配合

### 4.1 与 NarratorGenerator 配合

```python
# StoryPlotManager 提供上下文
state = plot_manager.get_current_state()
narrator_context = {
    "chapter_id": state.chapter_id,
    "node_id": state.current_node.id,
    "narrative_type": state.current_node.narration_type,
    "location": session.current_location,
    "is_exploring": state.is_exploring,
    "is_branch_point": state.node_type == NodeType.BRANCH
}

# NarratorGenerator 据此决定旁白类型和内容
narrator.generate(narrator_context)
```

### 4.2 与 OptionGenerator 配合

```python
# StoryPlotManager 告知当前选项状态
choices = plot_manager.get_available_choices()
if choices:
    # 处于分支点，强制用户选择
    option_generator.force_choice_mode(choices)
else:
    # 自由探索，使用对话穿插选项逻辑
    option_generator.normal_mode(interval=3-5)
```

### 4.3 与 NPCInteractionManager 配合

```python
# StoryPlotManager 在advance_to时通知
plot_manager.advance_to(node_id)

# 检查NPC交互触发器
events = plot_manager.check_triggers(context)
npc_manager.process_events(events)
```

### 4.4 与 EngineCore 配合

```python
# EngineCore.chat() 返回后
response = engine.chat(user_input, session_id)
state = plot_manager.get_current_state()

if state.node_type == NodeType.NARRATION_ONLY:
    # 仅旁白节点，自动推进
    plot_manager.advance_to(state.current_node.next)
elif state.is_branch_point:
    # 分支点，等待玩家选择
    pass
```

## 5. 章节配置文件格式

`assets/plot/{chapter_id}/chapter.yaml`:

```yaml
chapter:
  id: "chapter_01"
  name: "初到清溪镇"

nodes:
  - id: "n1"
    node_type: "NARRATION_ONLY"
    narration_type: "SCENE_ENTER"
    content: "你第一次来到清溪镇"

  - id: "n2"
    node_type: "DIALOGUE"
    npc_name: "guide"
    content: "欢迎来到清溪镇！"

  - id: "n3"
    node_type: "BRANCH"
    branches:
      - id: "b1"
        label: "询问咖啡馆在哪"
        condition: null
        next_node: "n4a"
      - id: "b2"
        label: "询问图书馆在哪"
        condition: null
        next_node: "n4b"
      - id: "b3"
        label: "（自由输入）"
        condition: null
        next_node: "n4c"

  - id: "n4a"
    node_type: "DIALOGUE"
    npc_name: "guide"
    content: "咖啡馆在镇中心广场东侧..."
```

## 6. Session 持久化扩展

```python
@dataclass
class PlotState:
    chapter_id: str
    node_id: str
    is_exploring: bool
    is_branch_point: bool
    queued_narrative: Optional[str]  # 预先触发的旁白

# Session 中新增字段
class ConversationSession:
    plot_state: PlotState
```
