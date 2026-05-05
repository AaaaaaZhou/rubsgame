"""
NPC主动交互管理器
管理 NPC 主动发起交互的混合触发机制
"""
import logging
from typing import Optional, Dict, List

from .types import (
    InteractionTrigger, NPCInteraction, InteractionQueue,
    PlotContext, Condition
)
from ...utils.logger import get_logger

_logger = get_logger("rubsgame.npc_interaction")

QUEUE_PRIORITY = {
    InteractionTrigger.STORY_NODE: 10,
    InteractionTrigger.LOCATION_CHANGE: 5,
    InteractionTrigger.RELATION_THRESHOLD: 3,
}


class NPCInteractionManager:
    """NPC 主动交互管理器"""

    def __init__(
        self,
        asset_manager,
        plot_manager,
        default_cooldown: int = 10
    ):
        """初始化

        Args:
            asset_manager: AssetManager 实例
            plot_manager: StoryPlotManager 实例
            default_cooldown: 默认冷却回合数
        """
        self._asset_mgr = asset_manager
        self._plot_mgr = plot_manager
        self._default_cooldown = default_cooldown

        # 触发器注册表
        self._story_triggers: Dict[str, NPCInteraction] = {}
        self._location_triggers: Dict[str, List[NPCInteraction]] = {}
        self._relation_triggers: Dict[str, List[NPCInteraction]] = {}

        # 冷却记录
        self._cooldown_records: Dict[str, int] = {}

        _logger.info("NPCInteractionManager initialized")

    def register_story_trigger(
        self,
        node_id: str,
        npc_name: str,
        content: Optional[str] = None,
        priority: int = 10
    ) -> None:
        """注册剧情节点触发器

        Args:
            node_id: 剧情节点ID
            npc_name: NPC名称
            content: 预定义的交互内容
            priority: 优先级
        """
        interaction = NPCInteraction(
            trigger=InteractionTrigger.STORY_NODE,
            npc_name=npc_name,
            priority=priority,
            content=content,
            cooldown_turns=self._default_cooldown
        )
        self._story_triggers[node_id] = interaction

    def register_location_trigger(
        self,
        location: str,
        npc_name: str,
        condition: Optional[Condition] = None,
        content: Optional[str] = None,
        priority: int = 5,
        cooldown_turns: int = 5
    ) -> None:
        """注册地点变化触发器

        Args:
            location: 地点名称
            npc_name: NPC名称
            condition: 可选条件
            content: 预定义的交互内容
            priority: 优先级
            cooldown_turns: 冷却回合数
        """
        interaction = NPCInteraction(
            trigger=InteractionTrigger.LOCATION_CHANGE,
            npc_name=npc_name,
            priority=priority,
            content=content,
            condition=condition,
            cooldown_turns=cooldown_turns
        )
        if location not in self._location_triggers:
            self._location_triggers[location] = []
        self._location_triggers[location].append(interaction)

    def register_relation_trigger(
        self,
        npc_name: str,
        condition: Condition,
        content: Optional[str] = None,
        priority: int = 3,
        cooldown_turns: int = 10
    ) -> None:
        """注册关系阈值触发器

        Args:
            npc_name: NPC名称
            condition: 关系条件（如 relationship_min=60）
            content: 预定义的交互内容
            priority: 优先级
            cooldown_turns: 冷却回合数
        """
        interaction = NPCInteraction(
            trigger=InteractionTrigger.RELATION_THRESHOLD,
            npc_name=npc_name,
            priority=priority,
            content=content,
            condition=condition,
            cooldown_turns=cooldown_turns
        )
        if npc_name not in self._relation_triggers:
            self._relation_triggers[npc_name] = []
        self._relation_triggers[npc_name].append(interaction)

    def check_and_queue_interactions(self, context: PlotContext) -> InteractionQueue:
        """检查所有触发条件，返回待执行的交互队列

        Args:
            context: 剧情上下文

        Returns:
            InteractionQueue 对象
        """
        queue = InteractionQueue()

        # 检查剧情节点触发
        self._check_story_triggers(context, queue)

        # 检查地点触发
        self._check_location_triggers(context, queue)

        # 检查关系阈值触发
        self._check_relation_triggers(context, queue)

        return queue

    def check_and_queue_interactions_from_plot_manager(
        self,
        context: PlotContext,
        location_triggers: Dict[str, List[NPCInteraction]],
        relation_triggers: Dict[str, List[NPCInteraction]]
    ) -> InteractionQueue:
        """从 PlotManager 获取触发器并检查（替代方案）"""
        queue = InteractionQueue()

        # STORY_NODE triggers
        for node_id, interaction in self._story_triggers.items():
            if node_id == context.current_node:
                if self._check_cooldown(interaction, context.conversation_turns):
                    queue.interactions.append(interaction)

        # Location triggers from PlotManager
        if context.current_location in location_triggers:
            for interaction in location_triggers[context.current_location]:
                if self._check_cooldown(interaction, context.conversation_turns):
                    queue.interactions.append(interaction)

        # Relation triggers from PlotManager
        for npc_name, interaction_list in relation_triggers.items():
            rel_value = context.relationship_states.get(npc_name, 0)
            for interaction in interaction_list:
                if self._check_relation_condition(interaction, rel_value):
                    if self._check_cooldown(interaction, context.conversation_turns):
                        queue.interactions.append(interaction)

        return queue

    def mark_interaction_done(self, npc_name: str, current_turn: int) -> None:
        """标记某 NPC 的交互已完成（进入冷却）

        Args:
            npc_name: NPC名称
            current_turn: 当前回合数
        """
        self._cooldown_records[npc_name] = current_turn
        _logger.debug(f"NPC {npc_name} interaction marked done, cooldown until turn {current_turn + self._default_cooldown}")

    def get_next_interaction(self, queue: InteractionQueue) -> Optional[NPCInteraction]:
        """获取队列中下一个待执行的交互

        Args:
            queue: 交互队列

        Returns:
            下一个 NPCInteraction 或 None
        """
        return queue.pop()

    def _check_story_triggers(self, context: PlotContext, queue: InteractionQueue) -> None:
        """检查剧情节点触发器"""
        interaction = self._story_triggers.get(context.current_node)
        if interaction:
            if self._check_cooldown(interaction, context.conversation_turns):
                queue.interactions.append(interaction)

    def _check_location_triggers(self, context: PlotContext, queue: InteractionQueue) -> None:
        """检查地点触发器"""
        triggers = self._location_triggers.get(context.current_location, [])
        for interaction in triggers:
            if self._check_cooldown(interaction, context.conversation_turns):
                queue.interactions.append(interaction)

    def _check_relation_triggers(self, context: PlotContext, queue: InteractionQueue) -> None:
        """检查关系阈值触发器"""
        for npc_name, triggers in self._relation_triggers.items():
            rel_value = context.relationship_states.get(npc_name, 0)
            for interaction in triggers:
                if self._check_relation_condition(interaction, rel_value):
                    if self._check_cooldown(interaction, context.conversation_turns):
                        queue.interactions.append(interaction)

    def _check_cooldown(self, interaction: NPCInteraction, current_turn: int) -> bool:
        """检查触发器是否在冷却中"""
        if interaction.npc_name not in self._cooldown_records:
            # Never triggered - allowed
            return True
        last_turn = self._cooldown_records[interaction.npc_name]
        return (current_turn - last_turn) >= interaction.cooldown_turns

    def _check_relation_condition(self, interaction: NPCInteraction, rel_value: int) -> bool:
        """检查关系条件是否满足"""
        if interaction.condition is None:
            return True

        cond = interaction.condition

        if cond.relationship_min is not None:
            if rel_value < cond.relationship_min:
                return False

        if cond.relationship_max is not None:
            if rel_value > cond.relationship_max:
                return False

        return True