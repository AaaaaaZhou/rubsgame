"""
剧情进度管理器
管理章节、节点推进、触发器检查
"""
import logging
from typing import Dict, List, Optional, Any

from .types import (
    Chapter, PlotNode, Branch, Trigger, TriggerType,
    PlotState, PlotContext, Condition,
    NodeType, NarrativeType, InteractionTrigger, NPCInteraction
)
from .plot_loader import PlotLoader


class StoryPlotManager:
    """剧情进度管理器"""

    def __init__(
        self,
        asset_manager,
        plot_dir: str = "assets/plot/",
        logger: Optional[logging.Logger] = None
    ):
        """初始化

        Args:
            asset_manager: AssetManager 实例，用于获取世界观地点
            plot_dir: 章节文件目录
            logger: 可选的日志记录器
        """
        self._asset_mgr = asset_manager
        self._plot_dir = plot_dir
        self._logger = logger or logging.getLogger("rubsgame.plot_manager")

        self._loader = PlotLoader(self._asset_mgr._file_reader, plot_dir, logger)
        self._chapters: Dict[str, Chapter] = {}
        self._current_chapter: Optional[Chapter] = None
        self._state = PlotState()

        # 触发器注册表
        self._location_triggers: Dict[str, List[NPCInteraction]] = {}
        self._relation_triggers: Dict[str, List[NPCInteraction]] = {}
        self._story_triggers: Dict[str, NPCInteraction] = {}

        self._logger.info("StoryPlotManager initialized")

    def load_chapter(self, chapter_id: str) -> Chapter:
        """加载章节"""
        chapter = self._loader.load(chapter_id)
        self._chapters[chapter_id] = chapter
        self._current_chapter = chapter

        self._state.chapter_id = chapter_id
        if chapter.nodes:
            self._state.node_id = chapter.nodes[0].id
            self._state.is_exploring = False
            self._state.is_branch_point = (chapter.nodes[0].node_type == NodeType.BRANCH)

        # 从章节配置加载 NPC_INTERACT 触发器
        self._load_npc_interactions_from_chapter(chapter)

        self._logger.info(f"Chapter '{chapter_id}' loaded: {len(chapter.nodes)} nodes")
        return chapter

    def _load_npc_interactions_from_chapter(self, chapter: Chapter) -> None:
        """从章节 YAML 加载 npc_interactions 配置"""
        try:
            import os
            chapter_dir = os.path.join(self._plot_dir, chapter.id)
            import yaml
            file_path = os.path.join(chapter_dir, "chapter.yaml")
            if not os.path.exists(file_path):
                return

            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            npc_interactions = data.get("npc_interactions", [])
            for item in npc_interactions:
                trigger_type_str = item.get("trigger_type", "")
                try:
                    trigger_type = InteractionTrigger(trigger_type_str.lower())
                except ValueError:
                    continue

                npc_name = item.get("npc_name", "")
                priority = item.get("priority", 5)
                content = item.get("content")
                location = item.get("location")
                threshold = item.get("threshold")
                cooldown = item.get("cooldown_turns", 10)

                interaction = NPCInteraction(
                    trigger=trigger_type,
                    npc_name=npc_name,
                    priority=priority,
                    content=content,
                    cooldown_turns=cooldown
                )

                if trigger_type == InteractionTrigger.LOCATION_CHANGE and location:
                    if location not in self._location_triggers:
                        self._location_triggers[location] = []
                    self._location_triggers[location].append(interaction)
                elif trigger_type == InteractionTrigger.RELATION_THRESHOLD and threshold:
                    interaction.condition = Condition(relationship_min=threshold)
                    if npc_name not in self._relation_triggers:
                        self._relation_triggers[npc_name] = []
                    self._relation_triggers[npc_name].append(interaction)

        except Exception as e:
            self._logger.warning(f"Failed to load npc_interactions from chapter {chapter.id}: {e}")

    def get_current_chapter(self) -> Optional[Chapter]:
        return self._current_chapter

    def get_current_state(self) -> PlotState:
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
        node = self._find_node(node_id)
        if node is None:
            raise ValueError(f"Node not found: {node_id}")

        self._state.node_id = node_id
        self._state.is_branch_point = (node.node_type == NodeType.BRANCH)
        self._state.is_exploring = False

        # 更新章节节点索引
        if self._current_chapter:
            for i, n in enumerate(self._current_chapter.nodes):
                if n.id == node_id:
                    self._current_chapter.current_node_index = i
                    break

        self._logger.debug(f"Advanced to node: {node_id} (type={node.node_type.value})")
        return node

    def make_choice(self, branch_id: str) -> PlotNode:
        """玩家选择分支后调用"""
        node = self.get_current_node()
        if not node or not node.branches:
            raise ValueError("Current node has no branches")

        branch = None
        for b in node.branches:
            if b.id == branch_id:
                branch = b
                break

        if branch is None:
            raise ValueError(f"Branch not found: {branch_id}")

        if not self._check_branch_condition(branch):
            raise ValueError(f"Branch condition not met: {branch_id}")

        self._state.is_branch_point = False
        return self.advance_to(branch.next_node)

    def get_available_choices(self) -> List[Branch]:
        """获取当前可用的分支选项"""
        node = self.get_current_node()
        if not node or not node.branches:
            return []

        return [b for b in node.branches if self._check_branch_condition(b)]

    def is_exploring(self) -> bool:
        """当前是否在自由探索模式"""
        return self._state.is_exploring

    def get_available_locations(self) -> List[str]:
        """获取玩家可前往的地点列表"""
        world = self._asset_mgr.get_current_world()
        if not world:
            return []
        return [loc.name for loc in world.locations]

    def move_to_location(self, location_name: str) -> bool:
        """玩家前往某地点，返回是否触发新剧情"""
        world = self._asset_mgr.get_current_world()
        if not world:
            return False

        location = world.get_location(location_name)
        if not location:
            return False

        self._state.is_exploring = True
        self._logger.debug(f"Moved to location: {location_name}")
        return True

    def check_triggers(self, context: PlotContext) -> List[Trigger]:
        """检查所有触发器，返回待触发的事件ID列表"""
        triggered = []
        node = self.get_current_node()
        if node:
            for trigger in node.triggers:
                if self._check_trigger_condition(trigger, context):
                    triggered.append(trigger)
        return triggered

    def register_trigger(
        self,
        trigger: Trigger,
        npc_name: Optional[str] = None,
        location: Optional[str] = None
    ) -> None:
        """注册新的触发器"""
        if trigger.type == TriggerType.LOCATION_CHANGE and location:
            if location not in self._location_triggers:
                self._location_triggers[location] = []
            # 转换为 NPCInteraction 形式存储
            self._location_triggers[location].append(NPCInteraction(
                trigger=InteractionTrigger.LOCATION_CHANGE,
                npc_name=npc_name or "",
                priority=5,
                condition=trigger.condition
            ))
        elif trigger.type == TriggerType.RELATION_THRESHOLD and npc_name:
            if npc_name not in self._relation_triggers:
                self._relation_triggers[npc_name] = []
            self._relation_triggers[npc_name].append(NPCInteraction(
                trigger=InteractionTrigger.RELATION_THRESHOLD,
                npc_name=npc_name,
                priority=5,
                condition=trigger.condition
            ))

    def get_location_triggers(self, location: str) -> List[NPCInteraction]:
        """获取某地点的 NPC 交互触发器"""
        return self._location_triggers.get(location, [])

    def get_relation_triggers(self, npc_name: str) -> List[NPCInteraction]:
        """获取某 NPC 的关系触发器"""
        return self._relation_triggers.get(npc_name, [])

    def _find_node(self, node_id: str) -> Optional[PlotNode]:
        if not self._current_chapter:
            return None
        for node in self._current_chapter.nodes:
            if node.id == node_id:
                return node
        return None

    def _check_branch_condition(self, branch: Branch) -> bool:
        """检查分支条件是否满足（目前仅为占位实现）"""
        return True

    def _check_trigger_condition(self, trigger: Trigger, context: PlotContext) -> bool:
        """检查触发器条件是否满足"""
        if trigger.condition is None:
            return True

        cond = trigger.condition

        if cond.relationship_min is not None:
            npc = context.relationship_states.get("")
            # 关系阈值检查由调用方在 NPCInteractionManager 中处理
            pass

        if cond.flag is not None:
            # 标志检查由调用方处理
            pass

        return True