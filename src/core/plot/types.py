"""
剧情系统共用数据类型
定义所有枚举、数据类，供 plot/ 下的所有模块共享
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any


# ==================== 节点与触发器枚举 ====================

class NodeType(Enum):
    """节点类型"""
    DIALOGUE = "dialogue"
    CHOICE = "choice"
    NARRATION_ONLY = "narration_only"
    BRANCH = "branch"
    NPC_INTERACT = "npc_interact"


class TriggerType(Enum):
    """触发器类型"""
    STORY_PROGRESS = "story_progress"
    LOCATION_CHANGE = "location_change"
    RELATION_THRESHOLD = "relation_threshold"


class NarrativeType(Enum):
    """旁白类型（StoryPlotManager 写入节点，NarratorGenerator 读取）"""
    SCENE_ENTER = "scene_enter"
    SCENE_EXIT = "scene_exit"
    EMOTION_BUILD = "emotion_build"
    TRANSITION = "transition"
    ACTION_RESULT = "action_result"
    CHAPTER_START = "chapter_start"
    CHAPTER_END = "chapter_end"
    FREE_EXPLORE = "free_explore"
    INNER_MONOLOGUE = "inner_monologue"


# ==================== 条件与分支 ====================

@dataclass
class Condition:
    """分支或触发器的条件"""
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


# ==================== 触发器 ====================

@dataclass
class Trigger:
    """事件触发器"""
    type: TriggerType
    condition: Optional[Condition] = None
    event: str = ""


# ==================== 剧情节点与章节 ====================

@dataclass
class PlotNode:
    """剧情节点"""
    id: str
    node_type: NodeType = NodeType.DIALOGUE
    npc_name: Optional[str] = None
    content: str = ""
    next: Optional[str] = None
    branches: Optional[List[Branch]] = None
    triggers: List[Trigger] = field(default_factory=list)
    narration_type: NarrativeType = NarrativeType.FREE_EXPLORE


@dataclass
class Chapter:
    """章节"""
    id: str
    name: str
    nodes: List[PlotNode] = field(default_factory=list)
    current_node_index: int = 0


# ==================== 剧情状态 ====================

@dataclass
class PlotState:
    """当前剧情状态（供 GameLoopController 和 Session 持久化使用）"""
    chapter_id: str = ""
    node_id: str = ""
    is_exploring: bool = False
    is_branch_point: bool = False
    queued_narrative: Optional[str] = None


# ==================== PlotContext（触发器检查上下文） ====================

@dataclass
class PlotContext:
    """传递给触发器检查的上下文"""
    current_chapter: str = ""
    current_node: str = ""
    current_location: str = ""
    conversation_turns: int = 0
    relationship_states: Dict[str, int] = field(default_factory=dict)


# ==================== NPC 主动交互 ====================

class InteractionTrigger(Enum):
    """NPC 交互触发类型"""
    STORY_NODE = "story_node"
    LOCATION_CHANGE = "location_change"
    RELATION_THRESHOLD = "relation_threshold"


@dataclass
class NPCInteraction:
    """NPC 主动交互事件"""
    trigger: InteractionTrigger
    npc_name: str
    priority: int = 5
    content: Optional[str] = None
    condition: Optional[Condition] = None
    cooldown_turns: int = 10
    last_triggered_turn: int = 0


@dataclass
class InteractionQueue:
    """NPC 交互事件队列"""
    interactions: List[NPCInteraction] = field(default_factory=list)

    def is_empty(self) -> bool:
        return len(self.interactions) == 0

    def pop(self) -> Optional[NPCInteraction]:
        if not self.interactions:
            return None
        self.interactions.sort(key=lambda x: x.priority, reverse=True)
        return self.interactions.pop(0)

    def peek(self) -> Optional[NPCInteraction]:
        if not self.interactions:
            return None
        self.interactions.sort(key=lambda x: x.priority, reverse=True)
        return self.interactions[0]


# ==================== 选项系统（OptionGenerator） ====================

class OptionType(Enum):
    """选项类型"""
    FIXED = "fixed"
    FREE_INPUT = "free_input"
    TRAVEL = "travel"


class OptionMode(Enum):
    """选项生成模式"""
    FORCE_CHOICE = "force_choice"
    NORMAL = "normal"
    TRAVEL = "travel"


@dataclass
class DialogOption:
    """对话选项"""
    type: OptionType
    content: str
    action: Optional[str] = None
    target: Optional[str] = None


@dataclass
class OptionOutput:
    """选项生成器输出"""
    options: List[DialogOption]
    mode: OptionMode = OptionMode.NORMAL
    expires_at: Optional[int] = None


# ==================== NarratorGenerator 输出 ====================

@dataclass
class NarrativeOutput:
    """旁白生成器输出"""
    text: str
    context: NarrativeType
    duration_hint: str = "medium"
    skip_allowed: bool = False