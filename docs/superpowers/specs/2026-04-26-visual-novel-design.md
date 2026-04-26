# 视觉小说模式设计文档

## 1. 概述

为 rubsgame 增加视觉小说风格的选项驱动机制，同时保留自由对话能力。系统以选项驱动为主，关键节点提供空白选项供玩家自由输入；NPC 可主动发起交互；旁白根据剧情状态自动生成。

## 2. 目标场景

- 角色扮演 + 交互式小说混合体验
- 主线有分支但最终收敛，章节制追踪进度
- 玩家行动以对话为主，可前往/探索已有地点，不改变世界状态
- NPC 主动交互采用混合触发（剧情节点 + 环境感知 + 关系驱动）

## 3. 架构概览

```
现有 EngineCore（不改动）
    ↑
    │ 事件回调
    │
┌─────────────────────────────────────────┐
│           StoryPlotManager              │
│  - 主线进度 / 章节状态 / 触发器队列       │
└─────────────────────────────────────────┘
    ↑                           ↓
    │                     ┌───────────┐
    │                     │ Narrator  │
    │                     │Generator  │
    │                     └───────────┘
    │                           │
┌────────────┐                  │
│    NPC     │← ─ ─ ─ ─ ─ ─ ─ ─┤
│Interaction │                  │
│  Manager   │                  │
└────────────┘                  ↓
    ↑                    ┌─────────────┐
    │                    │OptionGen-   │
    │                    │erator       │
    │                    └─────────────┘
    │                          │
    └──────────────────────────┘
              ↓
        PowerShellInterface
           (展示层)
```

## 4. 核心模块设计

### 4.1 StoryPlotManager（主线进度管理）

**职责：**
- 管理当前章节和主线进度
- 维护事件触发器队列
- 判断当前剧情状态（自由探索 / 章节节点 / 分支点）

**数据结构：**
```python
@dataclass
class Chapter:
    id: str
    name: str
    nodes: List[PlotNode]      # 章节内的剧情节点
    current_node_index: int

@dataclass
class PlotNode:
    id: str
    node_type: str             # "dialogue" | "choice" | "narration_only" | "branch"
    npc_name: Optional[str]    # 指定 NPC，不指定则由系统决定
    content: str               # 节点内容（可以是模板）
    next: Optional[str]       # 下一节点 ID（单线）
    branches: Optional[List[Branch]]  # 分支（多选一）
    triggers: List[Trigger]   # 触发条件

@dataclass
class Trigger:
    type: str                 # "story_progress" | "location" | "relationship" | "time"
    condition: Any
    event: str                # 触发的事件
```

**关键方法：**
- `get_current_state()` → PlotState（返回当前是自由探索还是章节节点）
- `advance_to(node_id)` → 更新进度
- `check_triggers(context)` → 返回待触发事件列表
- `get_available_locations()` → 玩家可前往的地点列表

### 4.2 NarratorGenerator（旁白生成器）

**职责：**
根据当前剧情状态，生成四类旁白：
- 场景描述："你走进咖啡馆，看到..."
- 情绪/氛围渲染：烘托当前情境
- 剧情过渡："与此同时..."、"几天后..."
- 行动描述：玩家空白选项执行后的结果描述

**生成策略：**
```python
class NarrativeContext(Enum):
    SCENE_ENTER      # 进入新场景
    SCENE_EXIT       # 离开场景
    EMOTION_BUILD    # 情绪铺垫
    TRANSITION       # 剧情过渡
    ACTION_RESULT    # 行动结果描述
    CHAPTER_START    # 章节开始
    CHAPTER_END      # 章节结束
```

**Prompt 模板：**
```
[System]
当前剧情状态：{narrative_context}
当前场景：{location}
当前情绪基调：{emotion}
主线进度：第{chapter}章 - {node_name}

请生成一段{narrative_context}类型的旁白，
长度为 {length} 句话/段落，
风格与当前{emotion}情绪一致。
```

**判断逻辑：**
- `SCENE_ENTER`：玩家位置变化时
- `EMOTION_BUILD`：连续 3 轮同情绪后自动插入
- `TRANSITION`：章节切换时
- `ACTION_RESULT`：玩家空白选项执行后
- `CHAPTER_START/END`：章节边界

### 4.3 OptionGenerator（选项生成器）

**触发时机：**
- **时机D - NPC提议后**：NPC 提出邀请/建议时，生成 [接受 / 拒绝 / 空白]
- **时机C - 对话中穿插**：每 3-5 轮对话后，随机出现分支选项

**选项类型：**
```python
@dataclass
class DialogOption:
    type: str           # "fixed" | "free_input"
    content: str         # 选项文字（fixed 类型）
    action: Optional[str]  # 执行动作（如 "travel_to"）

# NPC 提议后的选项
NPC_SUGGESTION_OPTIONS = [
    DialogOption(type="fixed", content="接受提议", action="accept"),
    DialogOption(type="fixed", content="拒绝提议", action="reject"),
    DialogOption(type="free_input", content="（自由输入）", action=None),
]

# 对话中穿插的选项（生成 2 个 + 1 个空白）
DialogOption(type="fixed", content="<LLM生成选项1>")
DialogOption(type="fixed", content="<LLM生成选项2>")
DialogOption(type="free_input", content="（自由输入）")
```

**生成 Prompt：**
```
基于当前对话上下文，生成 2 个符合角色性格的候选回复选项。
每个选项不超过 20 字。
选项应该是角色可能会说的话，而不是玩家想要说的话。
```

**与 EngineCore.chat 的交互：**
- 不替换 chat()，而是在 chat() 返回后判断是否需要生成选项
- 如果需要选项，将选项附加到返回结果中，由展示层渲染

### 4.4 NPCInteractionManager（Npc主动交互管理）

**触发条件检测：**
```python
class InteractionTrigger(Enum):
    STORY_NODE     # 剧情节点触发
    LOCATION_CHANGE # 环境感知（玩家进入某区域）
    RELATION_THRESHOLD  # 关系阈值触发
```

**事件队列机制：**
- 每轮对话结束后调用 `check_and_queue_interactions(session_context)`
- 将待触发的 NPC 交互加入队列
- 队列优先级：STORY_NODE > LOCATION_CHANGE > RELATION_THRESHOLD
- 下一轮优先处理队列中的 NPC 交互

**NPC 主动发言格式：**
```
[NPC名称]：<NPC发言内容>
[旁白（可选）]：<场景/氛围描述>
```

## 5. 对话流程重构

### 5.1 新的对话循环

```
┌─────────────────────────────────────────────────────────┐
│                     PowerShellInterface                  │
└─────────────────────────────────────────────────────────┘
                           ↓
                    获取玩家输入
                           ↓
        ┌────────────────────────────────────┐
        │         判断输入类型                 │
        └────────────────────────────────────┘
              ↓                    ↓
        [选项选择]              [自由输入]
              ↓                    ↓
        执行对应分支         EngineCore.chat()
              ↓                    ↓
        生成行动旁白          LLM 回复
        （如果有）                 ↓
              ↓           NarratorGenerator
                           判断是否需要旁白
                                  ↓
        ┌────────────────────────────────────┐
        │         StoryPlotManager            │
        │  - 检查触发器                       │
        │  - 更新章节进度                      │
        │  - 决定 NPC 是否主动交互             │
        └────────────────────────────────────┘
                                  ↓
        ┌────────────────────────────────────┐
        │       OptionGenerator               │
        │  - 判断是否生成选项                  │
        │  - 生成选项列表                      │
        └────────────────────────────────────┘
                                  ↓
                         展示给玩家
```

### 5.2 章节切换流程

```
章节结束节点
    ↓
NarratorGenerator 生成章节过渡旁白
    ↓
展示旁白 + "继续" 选项（或自动推进）
    ↓
StoryPlotManager 加载下一章节
    ↓
NarratorGenerator 生成新章节开场旁白
    ↓
进入新章节第一个节点
```

## 6. 数据结构扩展

### 6.1 PlotState

```python
@dataclass
class PlotState:
    chapter_id: str
    node_id: str
    is_exploring: bool        # 自由探索中
    is_branch_point: bool     # 是否在分支点
    available_choices: List[str]  # 当前可选的分支
```

### 6.2 Session 扩展字段

在 ConversationSession 中增加：
```python
@dataclass
class ConversationSession:
    # ... 现有字段 ...
    plot_state: PlotState
    npc_interaction_queue: List[NPCInteraction]
    option_pending: Optional[DialogOption]  # 当前悬挂的选项
```

## 7. 文件结构

```
src/
├── core/
│   └── plot/
│       ├── __init__.py
│       ├── plot_manager.py       # StoryPlotManager
│       ├── narrator.py           # NarratorGenerator
│       ├── option_generator.py   # OptionGenerator
│       └── npc_interaction.py     # NPCInteractionManager
└── ...
```

## 8. 实现顺序

1. **StoryPlotManager** — 章节和节点的数据结构、加载、进度追踪
2. **NarratorGenerator** — Prompt 模板和四类旁白生成逻辑
3. **OptionGenerator** — 选项生成、时机判断
4. **NPCInteractionManager** — 触发检测和事件队列
5. **PowerShellInterface 适配** — 选项渲染、键盘输入处理

## 9. 配置扩展

在 `config/settings.yaml` 中增加：

```yaml
visual_novel:
  option_interval: 3-5        # 多少轮对话后穿插选项
  auto_narration_emotion_threshold: 3  # 连续同情绪轮次后插入氛围旁白
  enable_npc_initiative: true  # 是否启用 NPC 主动交互

plot:
  chapters_dir: "assets/plot/"
```

## 10. 与现有系统的集成点

- **EngineCore.chat()** — 扩展返回结构，增加 `options` 和 `narrative` 字段
- **AssetManager** — 新增加载章节配置（PlotNode YAML）
- **SessionManager** — 持久化 plot_state 和 interaction_queue
- **MemoryManager** — 旁白和选项内容不进入记忆，仅对话内容进入
