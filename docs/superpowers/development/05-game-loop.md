# GameLoopController 开发指南

## 依赖关系

- **前置**: 所有其他模块（PlotManager, NarratorGenerator, OptionGenerator, NPCInteractionManager）
- **后续**: 被 PowerShellInterface 调用

## 核心概念

GameLoopController 是协调器，整合所有子模块。它处理：
- 对话循环流程控制
- 模式切换判断（选项模式 vs 自由输入）
- 各模块的调度时序

## 文件: src/core/plot/game_loop.py

```python
"""
GameLoopController - 对话循环协调器
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

from .plot_manager import StoryPlotManager
from .narrator import NarratorGenerator, NarrativeOutput
from .option_generator import OptionGenerator, OptionOutput, DialogOption, OptionMode, OptionType
from .npc_interaction import NPCInteractionManager
from .types import NarrativeContext, PlotContext, NodeType
from ..engine import EngineCore
from ..session import ConversationSession
from ..asset_manager import AssetManager
from ...clients.manager import ClientManager
from ...utils.logger import get_logger

_logger = get_logger("rubsgame.game_loop")


@dataclass
class GameLoopOutput:
    """游戏循环输出"""
    narrative: Optional[NarrativeOutput] = None
    options: Optional[OptionOutput] = None
    npc_response: Optional[str] = None
    is_game_over: bool = False


class EmotionTracker:
    """情绪追踪器"""

    def __init__(self, threshold: int = 3):
        self._count = 0
        self._last_emotion = None
        self._threshold = threshold

    def record(self, emotion: str) -> bool:
        """记录情绪，返回是否达到铺垫阈值"""
        if emotion == self._last_emotion:
            self._count += 1
        else:
            self._count = 1
            self._last_emotion = emotion
        return self._count >= self._threshold

    def reset(self):
        self._count = 0
        self._last_emotion = None


class GameLoopController:
    """对话循环协调器"""

    def __init__(
        self,
        engine: EngineCore,
        asset_manager: AssetManager,
        plot_manager: StoryPlotManager,
        client_manager: ClientManager
    ):
        self._engine = engine
        self._asset = asset_manager
        self._plot = plot_manager
        self._narrator = NarratorGenerator(client_manager)
        self._option_gen = OptionGenerator(client_manager)
        self._npc_mgr = NPCInteractionManager(asset_manager, plot_manager)
        self._emotion_tracker = EmotionTracker()

    def process_input(
        self,
        user_input: str,
        session: ConversationSession,
        is_option_selected: bool = False,
        selected_option: Optional[DialogOption] = None
    ) -> GameLoopOutput:
        """处理玩家输入，返回输出给展示层"""

        output = GameLoopOutput()

        # 1. 如果有选项待处理
        if session.option_pending:
            return self._handle_option_mode(session, selected_option)

        # 2. 如果是选项选择
        if is_option_selected and selected_option:
            return self._handle_option_selection(user_input, selected_option, session)

        # 3. 如果有NPC交互待处理
        if session.npc_interaction_queue and not session.npc_interaction_queue.is_empty():
            return self._handle_npc_interaction(session)

        # 4. 正常对话流程
        return self._handle_normal_dialog(user_input, session)

    def _handle_normal_dialog(
        self,
        user_input: str,
        session: ConversationSession
    ) -> GameLoopOutput:
        """处理正常对话"""
        output = GameLoopOutput()

        # 调用LLM
        response = self._engine.chat(user_input, session.session_id)

        # 更新情绪追踪
        should_emotion_build = self._emotion_tracker.record(response.get("emotion", "neutral"))

        # 检查是否需要行动结果旁白
        if response.get("action_taken"):
            output.narrative = self._narrator.generate(
                context=NarrativeContext.ACTION_RESULT,
                location=session.current_location,
                emotion=response.get("emotion", "neutral"),
                action_description=response.get("action_taken")
            )

        # 检查NPC提议
        if response.get("suggestion"):
            output.options = self._option_gen.generate_npc_suggestion_options(
                response["suggestion"]["type"]
            )
            session.npc_suggestion_pending = response["suggestion"]
            output.npc_response = response.get("content")
            return output

        # 检查触发器
        plot_context = self._build_plot_context(session)
        interaction_queue = self._npc_mgr.check_and_queue_interactions(plot_context)

        if not interaction_queue.is_empty():
            session.npc_interaction_queue = interaction_queue
            # 下一轮处理NPC交互

        # 检查是否生成对话穿插选项
        plot_state = self._plot.get_current_state()

        if self._option_gen.should_generate_option(
            session.turn_count,
            session.last_option_turn,
            session.npc_suggestion_pending is not None,
            plot_state.is_branch_point
        ):
            persona = self._asset.get_current_persona()
            output.options = self._option_gen.generate_in_conversation_options(
                chat_history=[msg.__dict__ for msg in session.full_history[-10:]],
                npc_name=session.bound_npc_id or "NPC",
                location=session.current_location,
                persona_system_prompt=persona.get_system_context() if persona else ""
            )
            session.last_option_turn = session.turn_count

        # 情绪铺垫旁白
        if should_emotion_build:
            narrative = self._narrator.generate(
                context=NarrativeContext.EMOTION_BUILD,
                location=session.current_location,
                emotion=response.get("emotion", "neutral"),
                chapter_name=plot_state.chapter_id,
                node_id=plot_state.node_id
            )
            # 情绪旁白不阻塞，可以和response一起返回
            output.narrative = narrative

        output.npc_response = response.get("content")
        return output

    def _handle_option_mode(
        self,
        session: ConversationSession,
        selected_option: Optional[DialogOption]
    ) -> GameLoopOutput:
        """处理选项模式"""
        if not selected_option:
            return GameLoopOutput()  # 等待选择

        return self._handle_option_selection("", selected_option, session)

    def _handle_option_selection(
        self,
        user_input: str,
        selected_option: DialogOption,
        session: ConversationSession
    ) -> GameLoopOutput:
        """处理选项选择"""
        output = GameLoopOutput()

        # 清除选项状态
        session.option_pending = None
        session.npc_suggestion_pending = None

        # 执行选项动作
        if selected_option.type == OptionType.TRAVEL:
            # 移动到新地点
            self._plot.move_to_location(selected_option.target)
            session.current_location = selected_option.target
            output.narrative = self._narrator.generate(
                context=NarrativeContext.SCENE_ENTER,
                location=selected_option.target,
                emotion="neutral"
            )
            return output

        elif selected_option.type == OptionType.FIXED:
            # 生成行动旁白
            output.narrative = self._narrator.generate(
                context=NarrativeContext.ACTION_RESULT,
                location=session.current_location,
                emotion=session.last_emotion,
                action_description=selected_option.content
            )

            # 如果是分支选择，更新剧情
            if selected_option.action == "branch":
                self._plot.make_choice(selected_option.target)

            # 如果是接受/拒绝，调用LLM处理
            if selected_option.action in ["accept", "reject"]:
                response = self._engine.chat(
                    f"[玩家选择: {selected_option.content}]",
                    session.session_id
                )
                output.npc_response = response.get("content")
                return output

        # 自由输入，使用用户输入作为对话
        if selected_option.type == OptionType.FREE_INPUT and user_input:
            response = self._engine.chat(user_input, session.session_id)
            output.npc_response = response.get("content")

        return output

    def _handle_npc_interaction(self, session: ConversationSession) -> GameLoopOutput:
        """处理NPC主动交互"""
        output = GameLoopOutput()

        interaction = self._npc_mgr.get_next_interaction(session.npc_interaction_queue)
        if not interaction:
            return self._handle_normal_dialog("", session)

        session.active_npc_interaction = interaction

        # 生成NPC出场
        if interaction.content:
            output.narrative = NarrativeOutput(
                text=interaction.content,
                context=NarrativeContext.SCENE_ENTER,
                duration_hint="short"
            )
        else:
            output.narrative = self._narrator.generate(
                context=NarrativeContext.SCENE_ENTER,
                location=session.current_location,
                npc_name=interaction.npc_name
            )

        # 触发NPC对话
        response = self._engine.chat(
            f"[NPC {interaction.npc_name} 主动搭话]",
            session.session_id
        )

        # 标记冷却
        self._npc_mgr.mark_interaction_done(interaction.npc_name, session.turn_count)

        output.npc_response = response.get("content")

        # 如果NPC提出提议，生成选项
        if response.get("suggestion"):
            output.options = self._option_gen.generate_npc_suggestion_options(
                response["suggestion"]["type"]
            )
            session.npc_suggestion_pending = response["suggestion"]

        return output

    def _build_plot_context(self, session: ConversationSession) -> PlotContext:
        """构建PlotContext"""
        plot_state = self._plot.get_current_state()
        return PlotContext(
            current_chapter=plot_state.chapter_id,
            current_node=plot_state.node_id,
            current_location=session.current_location or "未知",
            conversation_turns=session.turn_count,
            relationship_states=session.npc_relationships or {}
        )
```

## 与展示层配合

PowerShellInterface 调用方式：

```python
# interface/ps_shell.py 中

class PowerShellInterface:
    def __init__(self, engine: EngineCore, dev_mode: bool = False):
        self._engine = engine
        self._dev_mode = dev_mode
        self._game_loop: Optional[GameLoopController] = None

    def _init_game_loop(self):
        """延迟初始化GameLoopController"""
        if self._game_loop is None:
            self._game_loop = GameLoopController(
                engine=self._engine,
                asset_manager=AssetManager.get_instance(),
                plot_manager=...,  # 需要初始化
                client_manager=ClientManager.get_instance()
            )

    def run_repl(self):
        while True:
            user_input = self._read_input()

            if user_input.lower() in ['quit', 'exit']:
                break

            output = self._game_loop.process_input(
                user_input,
                session=self._current_session
            )

            self._display_output(output)

    def _display_output(self, output: GameLoopOutput):
        """展示输出"""
        if output.narrative:
            print(f"\n【旁白】{output.narrative.text}\n")

        if output.npc_response:
            print(f"{output.npc_response}\n")

        if output.options:
            print("你会怎么做？")
            for i, opt in enumerate(output.options.options, 1):
                print(f"  {i}. {opt.content}")

    def _read_input(self) -> str:
        """读取用户输入"""
        # 正常输入或选项选择
        pass
```

## 模式切换逻辑

```
┌─────────────────────────────────────────────┐
│                  当前状态                    │
├─────────────────────────────────────────────┤
│  session.option_pending                      │
│    │  有选项待选择 → 显示选项，等待选择          │
│    ▼                                        │
│  session.npc_interaction_queue               │
│    │  有NPC交互 → 处理NPC交互                  │
│    ▼                                        │
│  is_option_selected                          │
│    │  选择了选项 → 处理选项结果                 │
│    ▼                                        │
│  正常对话 → EngineCore.chat() → 决定是否生成选项│
└─────────────────────────────────────────────┘
```

## 测试用例骨架

```python
# unittest/core/plot/test_game_loop.py
import pytest
from unittest.mock import Mock, MagicMock
from src.core.plot.game_loop import GameLoopController, EmotionTracker, GameLoopOutput


class TestEmotionTracker:
    def test_same_emotion_accumulates(self):
        tracker = EmotionTracker(threshold=3)
        assert not tracker.record("happy")
        assert not tracker.record("happy")
        assert tracker.record("happy")  # 第三次，应该返回True

    def test_different_emotion_resets(self):
        tracker = EmotionTracker(threshold=3)
        tracker.record("happy")
        tracker.record("happy")
        tracker.record("sad")  # 情绪变化，重置
        assert not tracker.record("sad")


class TestGameLoopController:
    @pytest.fixture
    def mock_engine(self):
        return Mock()

    @pytest.fixture
    def mock_asset_manager(self):
        return Mock()

    @pytest.fixture
    def mock_plot_manager(self):
        return Mock()

    @pytest.fixture
    def mock_client_manager(self):
        manager = Mock()
        manager.get_client.return_value = Mock()
        return manager

    def test_process_input_normal_dialog(
        self, mock_engine, mock_asset_manager, mock_plot_manager, mock_client_manager
    ):
        controller = GameLoopController(
            mock_engine, mock_asset_manager, mock_plot_manager, mock_client_manager
        )

        mock_engine.chat.return_value = {
            "content": "你好！",
            "emotion": "happy",
            "intensity": 0.8
        }

        session = Mock()
        session.session_id = "test"
        session.turn_count = 0
        session.option_pending = None
        session.npc_interaction_queue = None

        output = controller.process_input("你好", session)
        assert isinstance(output, GameLoopOutput)
```

## 初始化顺序

```python
# src/core/plot/__init__.py
from .types import Chapter, PlotNode, PlotState, PlotContext, NodeType, NarrativeType
from .narrator import NarratorGenerator, NarrativeOutput
from .option_generator import OptionGenerator, OptionOutput, DialogOption, OptionType, OptionMode
from .npc_interaction import NPCInteractionManager, InteractionQueue, NPCInteraction, InteractionTrigger
from .game_loop import GameLoopController, GameLoopOutput

__all__ = [
    "Chapter", "PlotNode", "PlotState", "PlotContext", "NodeType", "NarrativeType",
    "NarratorGenerator", "NarrativeOutput",
    "OptionGenerator", "OptionOutput", "DialogOption", "OptionType", "OptionMode",
    "NPCInteractionManager", "InteractionQueue", "NPCInteraction", "InteractionTrigger",
    "GameLoopController", "GameLoopOutput"
]
```
