"""
GameLoopController
协调所有子模块，对话循环控制入口
"""
import logging
from dataclasses import dataclass
from typing import Optional

from .types import (
    PlotState, PlotContext, NarrativeType, NarrativeOutput,
    OptionOutput, OptionMode, DialogOption, OptionType,
    InteractionQueue, NPCInteraction
)
from .narrator import NarratorGenerator
from .option_generator import OptionGenerator
from .npc_interaction import NPCInteractionManager
from ...clients.manager import ClientManager
from ...utils.logger import get_logger

_logger = get_logger("rubsgame.game_loop")


class EmotionTracker:
    """情绪追踪器 - 检测连续同情绪触发旁白"""

    def __init__(self, threshold: int = 3):
        self._threshold = threshold
        self._emotion_counts: dict = {}
        self._last_emotion: Optional[str] = None

    def record(self, emotion: str) -> bool:
        """记录情绪，返回是否达到触发阈值"""
        if emotion == self._last_emotion:
            self._emotion_counts[emotion] = self._emotion_counts.get(emotion, 0) + 1
        else:
            self._emotion_counts = {emotion: 1}
            self._last_emotion = emotion

        return self._emotion_counts.get(emotion, 0) >= self._threshold

    def reset(self) -> None:
        self._emotion_counts = {}
        self._last_emotion = None


@dataclass
class GameLoopOutput:
    """GameLoop 输出"""
    narrative: Optional[NarrativeOutput] = None
    options: Optional[OptionOutput] = None
    npc_response: Optional[str] = None
    is_game_over: bool = False


class GameLoopController:
    """游戏循环控制器"""

    def __init__(
        self,
        engine,
        asset_manager,
        plot_manager,
        client_manager: ClientManager,
        narrator_model: str = "minimax_m2_her",
        option_model: str = "minimax_m2_her"
    ):
        """初始化

        Args:
            engine: EngineCore 实例
            asset_manager: AssetManager 实例
            plot_manager: StoryPlotManager 实例
            client_manager: ClientManager 实例
            narrator_model: NarratorGenerator 使用的模型
            option_model: OptionGenerator 使用的模型
        """
        self._engine = engine
        self._asset_mgr = asset_manager
        self._plot_mgr = plot_manager
        self._client_mgr = client_manager

        # 初始化子模块
        self._narrator = NarratorGenerator(client_manager, narrator_model)
        self._option_gen = OptionGenerator(client_manager, option_model)
        self._npc_mgr = NPCInteractionManager(asset_manager, plot_manager)

        # 状态
        self._emotion_tracker = EmotionTracker(threshold=3)
        self._npc_interaction_queue: InteractionQueue = InteractionQueue()
        self._pending_narrative: Optional[NarrativeOutput] = None

        _logger.info("GameLoopController initialized")

    def process_input(
        self,
        user_input: str,
        session,
        is_option_selected: bool = False,
        selected_option: Optional[DialogOption] = None
    ) -> GameLoopOutput:
        """主入口 - 处理用户输入

        Args:
            user_input: 用户输入文本
            session: ConversationSession
            is_option_selected: 是否为选项选择模式
            selected_option: 选中的选项

        Returns:
            GameLoopOutput 对象
        """
        # 1. 检查是否有待处理的 NPC 交互
        if not self._npc_interaction_queue.is_empty():
            return self._handle_npc_interaction(session)

        # 2. 检查是否有待显示的旁白
        if self._pending_narrative:
            narrative = self._pending_narrative
            self._pending_narrative = None
            return GameLoopOutput(narrative=narrative)

        # 3. 分支点 - 等待玩家选择
        state = self._plot_mgr.get_current_state()
        if state.is_branch_point and not is_option_selected:
            choices = self._plot_mgr.get_available_choices()
            options = self._option_gen.generate_branch_options(choices)
            return GameLoopOutput(options=options)

        # 4. 处理选项选择
        if is_option_selected and selected_option:
            return self._handle_option_selection(user_input, selected_option, session)

        # 5. 处理自由输入（进入对话模式）
        return self._handle_normal_dialog(user_input, session)

    def _handle_normal_dialog(
        self,
        user_input: str,
        session
    ) -> GameLoopOutput:
        """处理普通对话"""
        # 调用 EngineCore.chat()
        response = self._engine.chat(user_input, session.session_id)

        # 更新情绪追踪
        emotion = response.get("emotion", "neutral")
        should_narrate_emotion = self._emotion_tracker.record(emotion)
        session.turn_count += 1
        session.last_emotion = emotion

        # 决定是否有 ACTION_RESULT 旁白
        narrative = None
        if user_input and not user_input.startswith("/"):
            narrative = self._narrator.generate(
                context=NarrativeType.ACTION_RESULT,
                emotion=emotion,
                action_description=user_input
            )

        # 检查 NPC 交互触发
        context = self._build_plot_context(session)
        queue = self._npc_mgr.check_and_queue_interactions(context)
        if not queue.is_empty():
            self._npc_interaction_queue = queue

        # 决定是否生成对话选项
        options = None
        state = self._plot_mgr.get_current_state()
        should_gen = self._option_gen.should_generate_option(
            conversation_turns=session.turn_count,
            last_option_turn=session.last_option_turn,
            npc_suggestion_pending=session.npc_suggestion_pending is not None,
            is_branch_point=state.is_branch_point
        )
        if should_gen:
            options = self._option_gen.generate_in_conversation_options(
                chat_history=[msg.to_dict() for msg in session.full_history[-10:]],
                npc_name=self._asset_mgr.get_current_npc().persona.name if self._asset_mgr.get_current_npc() else "NPC",
                location=session.current_location or "老街"
            )
            session.last_option_turn = session.turn_count

        return GameLoopOutput(
            narrative=narrative,
            options=options,
            npc_response=response.get("content")
        )

    def _handle_option_selection(
        self,
        user_input: str,
        selected_option: DialogOption,
        session
    ) -> GameLoopOutput:
        """处理选项选择"""
        session.option_pending = None

        if selected_option.type == OptionType.TRAVEL:
            # 旅行选项
            location = selected_option.target
            self._plot_mgr.move_to_location(location)
            session.current_location = location

            narrative = self._narrator.generate(
                context=NarrativeType.SCENE_ENTER,
                location=location,
                emotion="neutral"
            )
            return GameLoopOutput(narrative=narrative)

        elif selected_option.type == OptionType.FIXED:
            if selected_option.action == "accept":
                session.npc_suggestion_pending = None
                # 接受 NPC 提议，生成确认旁白
                narrative = self._narrator.generate(
                    context=NarrativeType.ACTION_RESULT,
                    emotion="happy",
                    action_description="接受了提议"
                )
                return GameLoopOutput(narrative=narrative)

            elif selected_option.action == "reject":
                session.npc_suggestion_pending = None
                narrative = self._narrator.generate(
                    context=NarrativeType.ACTION_RESULT,
                    emotion="neutral",
                    action_description="礼貌拒绝了提议"
                )
                return GameLoopOutput(narrative=narrative)

            elif selected_option.action == "branch":
                # 分支选择
                try:
                    node = self._plot_mgr.make_choice(selected_option.target)
                    return self._handle_node_advance(node, session)
                except ValueError as e:
                    _logger.warning(f"Invalid branch selection: {e}")
                    return GameLoopOutput()

        elif selected_option.type == OptionType.FREE_INPUT:
            if selected_option.action == "free_input":
                # 空白选项：传递用户输入给对话引擎
                return self._handle_normal_dialog(user_input, session)

        return GameLoopOutput()

    def _handle_npc_interaction(self, session) -> GameLoopOutput:
        """处理 NPC 主动交互"""
        interaction = self._npc_mgr.get_next_interaction(self._npc_interaction_queue)
        if interaction is None:
            return GameLoopOutput()

        # 生成 NPC 出场旁白
        narrative = self._narrator.generate(
            context=NarrativeType.SCENE_ENTER,
            location=session.current_location,
            emotion="neutral",
            npc_name=interaction.npc_name
        )

        # 标记冷却
        self._npc_mgr.mark_interaction_done(interaction.npc_name, session.turn_count)

        # 设置 NPC 建议待处理
        session.npc_suggestion_pending = {
            "npc_name": interaction.npc_name,
            "content": interaction.content
        }

        # 生成接受/拒绝选项
        options = self._option_gen.generate_npc_suggestion_options()

        return GameLoopOutput(
            narrative=narrative,
            options=options,
            npc_response=interaction.content
        )

    def _handle_node_advance(self, node, session) -> GameLoopOutput:
        """推进到新节点后的处理"""
        state = self._plot_mgr.get_current_state()

        # 生成节点旁白
        narrative = None
        if node.narration_type != NarrativeType.FREE_EXPLORE:
            narrative = self._narrator.generate(
                context=node.narration_type,
                location=session.current_location,
                emotion="neutral",
                chapter_name=state.chapter_id,
                node_id=node.id
            )

        # 检查节点类型
        node_type_name = node.node_type.name if hasattr(node.node_type, 'name') else str(node.node_type)
        if node_type_name == "NARRATION_ONLY":
            # 仅旁白节点，自动推进
            if node.next:
                next_node = self._plot_mgr.advance_to(node.next)
                return self._handle_node_advance(next_node, session)
            else:
                return GameLoopOutput(narrative=narrative, is_game_over=True)

        elif node_type_name == "NPC_INTERACT":
            # NPC 交互节点
            if node.npc_name and node.content:
                npc_response = node.content
                narrative = self._narrator.generate(
                    context=NarrativeType.CHAPTER_START,
                    location=session.current_location,
                    emotion="neutral",
                    npc_name=node.npc_name
                )
                # 注册剧情触发器
                self._npc_mgr.register_story_trigger(
                    node_id=node.id,
                    npc_name=node.npc_name,
                    content=npc_response
                )

                # 设置 NPC 建议
                session.npc_suggestion_pending = {
                    "npc_name": node.npc_name,
                    "content": npc_response
                }

                options = self._option_gen.generate_npc_suggestion_options()
                return GameLoopOutput(
                    narrative=narrative,
                    options=options,
                    npc_response=npc_response
                )

        elif node_type_name == "BRANCH":
            choices = self._plot_mgr.get_available_choices()
            options = self._option_gen.generate_branch_options(choices)
            return GameLoopOutput(options=options, narrative=narrative)

        elif node_type_name == "DIALOGUE":
            # 对话节点，显示 NPC 内容
            return GameLoopOutput(
                narrative=narrative,
                npc_response=node.content
            )

        return GameLoopOutput(narrative=narrative)

    def _build_plot_context(self, session) -> PlotContext:
        """构建 PlotContext"""
        state = self._plot_mgr.get_current_state()
        return PlotContext(
            current_chapter=state.chapter_id,
            current_node=state.node_id,
            current_location=session.current_location or "",
            conversation_turns=session.turn_count,
            relationship_states=session.npc_relationships
        )

    def start_chapter(self, chapter_id: str, session) -> GameLoopOutput:
        """开始章节"""
        chapter = self._plot_mgr.load_chapter(chapter_id)

        # 生成章节开始旁白
        narrative = self._narrator.generate(
            context=NarrativeType.CHAPTER_START,
            location=session.current_location,
            emotion="neutral",
            chapter_name=chapter.name,
            node_id=chapter.nodes[0].id if chapter.nodes else ""
        )

        if chapter.nodes:
            first_node = chapter.nodes[0]
            return self._handle_node_advance(first_node, session)

        return GameLoopOutput(narrative=narrative)