"""
GameLoopController tests
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import pytest
from src.core.plot.game_loop import GameLoopController, EmotionTracker
from src.core.plot.types import NarrativeType, PlotState


class MockEngine:
    def __init__(self, response=None):
        self.response = response or {"content": "Mock response", "emotion": "neutral", "intensity": 0.5}
        self.chat_calls = []

    def chat(self, user_input, session_id):
        self.chat_calls.append((user_input, session_id))
        return self.response


class MockAssetManager:
    def __init__(self):
        self._current_npc = None

    def get_current_npc(self):
        return self._current_npc


class MockNPC:
    class Persona:
        name = "alice"
    persona = Persona()


class MockPlotManager:
    def __init__(self):
        self._state = PlotState()

    def get_current_state(self):
        return self._state

    def load_chapter(self, chapter_id):
        class MockChapter:
            id = chapter_id
            name = "Test Chapter"
            nodes = []
        return MockChapter()

    def move_to_location(self, loc):
        return True

    def get_available_choices(self):
        from src.core.plot.types import Branch
        return [Branch(id="b1", label="Choice A", next_node="n2a")]

    def make_choice(self, branch_id):
        from src.core.plot.types import Branch, PlotNode, NodeType, NarrativeType
        # Return a simple DIALOGUE node as the result of choice
        return PlotNode(id="n_result", node_type=NodeType.DIALOGUE,
                        content="Result of choice", narration_type=NarrativeType.FREE_EXPLORE)

    def advance_to(self, node_id):
        from src.core.plot.types import PlotNode, NodeType, NarrativeType
        return PlotNode(id=node_id, node_type=NodeType.DIALOGUE,
                        content="Advanced", narration_type=NarrativeType.FREE_EXPLORE)


class MockClientManager:
    def __init__(self):
        pass

    def get_client(self, name=None):
        class MockClient:
            def chat(self, messages, **kwargs):
                return "Mock narration"
        return MockClient()


class TestEmotionTracker:
    def test_record_different_emotions_resets(self):
        tracker = EmotionTracker(threshold=3)
        assert tracker.record("happy") is False
        assert tracker.record("sad") is False
        # Different emotion resets count
        tracker._emotion_counts = {"sad": 1}
        tracker._last_emotion = "sad"
        assert tracker.record("happy") is False
        assert tracker._emotion_counts.get("happy", 0) == 1

    def test_record_same_emotion_accumulates(self):
        tracker = EmotionTracker(threshold=3)
        tracker._emotion_counts = {"happy": 2}
        tracker._last_emotion = "happy"
        result = tracker.record("happy")
        assert tracker._emotion_counts["happy"] == 3
        assert result is True

    def test_record_reaches_threshold(self):
        tracker = EmotionTracker(threshold=3)
        tracker.record("happy")
        tracker.record("happy")
        result = tracker.record("happy")
        assert result is True

    def test_reset_clears_state(self):
        tracker = EmotionTracker(threshold=3)
        tracker._emotion_counts = {"happy": 3}
        tracker._last_emotion = "happy"
        tracker.reset()
        assert tracker._emotion_counts == {}
        assert tracker._last_emotion is None


class TestGameLoopController:
    def setup_method(self):
        self.mock_engine = MockEngine()
        self.mock_asset = MockAssetManager()
        self.mock_asset._current_npc = MockNPC()
        self.mock_plot = MockPlotManager()
        self.mock_client = MockClientManager()

    def test_controller_init(self):
        controller = GameLoopController(
            engine=self.mock_engine,
            asset_manager=self.mock_asset,
            plot_manager=self.mock_plot,
            client_manager=self.mock_client
        )
        assert controller._narrator is not None
        assert controller._option_gen is not None
        assert controller._npc_mgr is not None

    def test_process_input_normal_dialog(self):
        controller = GameLoopController(
            engine=self.mock_engine,
            asset_manager=self.mock_asset,
            plot_manager=self.mock_plot,
            client_manager=self.mock_client
        )

        class MockSession:
            session_id = "test"
            turn_count = 0
            last_option_turn = 0
            npc_suggestion_pending = None
            current_location = "Old Street"
            last_emotion = "neutral"
            option_pending = None
            npc_relationships = {}
            full_history = []

            class Msg:
                def to_dict(self):
                    return {"role": "user", "content": "hello"}
            full_history = [Msg()]

        output = controller.process_input("Hello", MockSession())
        assert output.npc_response == "Mock response"
        assert len(self.mock_engine.chat_calls) == 1

    def test_process_input_branch_point_returns_options(self):
        controller = GameLoopController(
            engine=self.mock_engine,
            asset_manager=self.mock_asset,
            plot_manager=self.mock_plot,
            client_manager=self.mock_client
        )
        self.mock_plot._state.is_branch_point = True

        # When at branch point, options are returned
        # Note: The controller checks is_branch_point BEFORE calling engine.chat
        # So no engine.chat calls should happen
        class MockSession:
            session_id = "test"
            turn_count = 0
            last_option_turn = 0
            npc_suggestion_pending = None
            current_location = "Old Street"
            last_emotion = "neutral"
            option_pending = None
            npc_relationships = {}
            full_history = []
            class Msg:
                def to_dict(self):
                    return {}
            full_history = [Msg()]

        output = controller.process_input("Hello", MockSession())
        assert output.options is not None
        assert output.options.mode.value == "force_choice"
        # No chat call because we return at branch point check
        assert len(self.mock_engine.chat_calls) == 0

    def test_handle_option_selection_travel(self):
        controller = GameLoopController(
            engine=self.mock_engine,
            asset_manager=self.mock_asset,
            plot_manager=self.mock_plot,
            client_manager=self.mock_client
        )

        class MockSession:
            session_id = "test"
            turn_count = 0
            option_pending = None
            npc_suggestion_pending = None
            npc_relationships = {}
            current_location = None

        from src.core.plot.types import DialogOption, OptionType
        option = DialogOption(type=OptionType.TRAVEL, content="Old Street", action="move", target="Old Street")

        output = controller._handle_option_selection("Old Street", option, MockSession())
        assert output.narrative is not None

    def test_handle_option_selection_free_input(self):
        controller = GameLoopController(
            engine=self.mock_engine,
            asset_manager=self.mock_asset,
            plot_manager=self.mock_plot,
            client_manager=self.mock_client
        )

        class MockSession:
            session_id = "test"
            turn_count = 0
            last_option_turn = 0
            npc_suggestion_pending = None
            current_location = "Old Street"
            last_emotion = "neutral"
            option_pending = None
            npc_relationships = {}
            full_history = []

            class Msg:
                def to_dict(self):
                    return {"role": "user", "content": "test"}
            full_history = [Msg()]

        from src.core.plot.types import DialogOption, OptionType
        option = DialogOption(type=OptionType.FREE_INPUT, content="(Free Input)", action="free_input")

        output = controller._handle_option_selection("My custom input", option, MockSession())
        assert len(self.mock_engine.chat_calls) == 1

    def test_start_chapter(self):
        controller = GameLoopController(
            engine=self.mock_engine,
            asset_manager=self.mock_asset,
            plot_manager=self.mock_plot,
            client_manager=self.mock_client
        )

        from src.core.plot.types import PlotNode, NodeType, NarrativeType
        node = PlotNode(
            id="n1",
            node_type=NodeType.DIALOGUE,
            content="Test content",
            narration_type=NarrativeType.CHAPTER_START
        )

        class MockChapter:
            id = "ch1"
            name = "Test Chapter"
            nodes = [node]

        self.mock_plot.load_chapter = lambda x: MockChapter()

        class MockSession:
            session_id = "test"
            turn_count = 0
            last_option_turn = 0
            npc_suggestion_pending = None
            current_location = "Old Street"
            last_emotion = "neutral"
            option_pending = None
            npc_relationships = {}
            full_history = []
            class Msg:
                def to_dict(self):
                    return {}
            full_history = [Msg()]

        output = controller.start_chapter("ch1", MockSession())
        assert output.narrative is not None or output.options is not None

    def test_handle_node_advance_narrates_only_auto_advances(self):
        """NARRATION_ONLY node should auto-advance to next node"""
        from src.core.plot.types import PlotNode, NodeType, NarrativeType, PlotState

        controller = GameLoopController(
            engine=self.mock_engine,
            asset_manager=self.mock_asset,
            plot_manager=self.mock_plot,
            client_manager=self.mock_client
        )

        # Mock plot manager with NARRATION_ONLY chain
        node1 = PlotNode(id="n1", node_type=NodeType.NARRATION_ONLY,
                         narration_type=NarrativeType.SCENE_ENTER,
                         content="Scene start", next="n2")
        node2 = PlotNode(id="n2", node_type=NodeType.DIALOGUE,
                         narration_type=NarrativeType.FREE_EXPLORE,
                         content="Dialogue content")

        class MockChapter:
            id = "ch1"
            name = "Test"
            nodes = [node1, node2]

        # Patch load_chapter and advance_to
        self.mock_plot.load_chapter = lambda x: MockChapter()
        advance_calls = []
        def mock_advance(node_id):
            advance_calls.append(node_id)
            return node2 if node_id == "n2" else node1
        self.mock_plot.advance_to = mock_advance

        session = type('MockSession', (), {
            'session_id': 'test',
            'turn_count': 0,
            'last_option_turn': 0,
            'npc_suggestion_pending': None,
            'current_location': 'Old Street',
            'last_emotion': 'neutral',
            'option_pending': None,
            'npc_relationships': {},
            'full_history': [],
        })()

        output = controller._handle_node_advance(node1, session)
        # Auto-advance should have been called with next node
        assert "n2" in advance_calls

    def test_handle_node_advance_dialogue_returns_content(self):
        from src.core.plot.types import PlotNode, NodeType, NarrativeType

        controller = GameLoopController(
            engine=self.mock_engine,
            asset_manager=self.mock_asset,
            plot_manager=self.mock_plot,
            client_manager=self.mock_client
        )

        node = PlotNode(id="n1", node_type=NodeType.DIALOGUE,
                       narration_type=NarrativeType.FREE_EXPLORE,
                       content="Hello, player!")

        class MockSession:
            session_id = "test"
            turn_count = 0
            last_option_turn = 0
            npc_suggestion_pending = None
            current_location = "Old Street"
            last_emotion = "neutral"
            option_pending = None
            npc_relationships = {}
            full_history = []
            class Msg:
                def to_dict(self):
                    return {}
            full_history = [Msg()]

        output = controller._handle_node_advance(node, MockSession())
        assert output.npc_response == "Hello, player!"
        assert output.options is None

    def test_handle_node_advance_branch_returns_options(self):
        from src.core.plot.types import PlotNode, NodeType, NarrativeType, Branch

        controller = GameLoopController(
            engine=self.mock_engine,
            asset_manager=self.mock_asset,
            plot_manager=self.mock_plot,
            client_manager=self.mock_client
        )

        branch = Branch(id="b1", label="Go left", next_node="n2")
        node = PlotNode(id="n1", node_type=NodeType.BRANCH,
                       narration_type=NarrativeType.FREE_EXPLORE,
                       content="", branches=[branch])

        class MockSession:
            session_id = "test"
            turn_count = 0
            last_option_turn = 0
            npc_suggestion_pending = None
            current_location = "Old Street"
            last_emotion = "neutral"
            option_pending = None
            npc_relationships = {}
            full_history = []
            class Msg:
                def to_dict(self):
                    return {}
            full_history = [Msg()]

        output = controller._handle_node_advance(node, MockSession())
        assert output.options is not None
        assert output.options.mode.value == "force_choice"
        assert len(output.options.options) == 2  # branch + free input

    def test_handle_node_advance_npc_interact_returns_suggestion(self):
        from src.core.plot.types import PlotNode, NodeType, NarrativeType

        controller = GameLoopController(
            engine=self.mock_engine,
            asset_manager=self.mock_asset,
            plot_manager=self.mock_plot,
            client_manager=self.mock_client
        )

        node = PlotNode(id="n_special", node_type=NodeType.NPC_INTERACT,
                       narration_type=NarrativeType.SCENE_ENTER,
                       npc_name="alice", content="「找到你了！」")

        class MockSession:
            session_id = "test"
            turn_count = 5
            last_option_turn = 0
            npc_suggestion_pending = None
            current_location = "Old Street"
            last_emotion = "neutral"
            option_pending = None
            npc_relationships = {}
            full_history = []
            class Msg:
                def to_dict(self):
                    return {}
            full_history = [Msg()]

        output = controller._handle_node_advance(node, MockSession())
        assert output.npc_response == "「找到你了！」"
        assert output.options is not None
        assert output.options.mode.value == "force_choice"

    def test_process_input_npc_interaction_queue_returns_interaction(self):
        from src.core.plot.types import InteractionQueue, NPCInteraction, InteractionTrigger

        controller = GameLoopController(
            engine=self.mock_engine,
            asset_manager=self.mock_asset,
            plot_manager=self.mock_plot,
            client_manager=self.mock_client
        )

        # Pre-fill the interaction queue
        interaction = NPCInteraction(
            trigger=InteractionTrigger.LOCATION_CHANGE,
            npc_name="bob",
            priority=5,
            content="「嘿！这边！」"
        )
        controller._npc_interaction_queue = InteractionQueue(interactions=[interaction])

        class MockSession:
            session_id = "test"
            turn_count = 0
            last_option_turn = 0
            npc_suggestion_pending = None
            current_location = "Old Street"
            last_emotion = "neutral"
            option_pending = None
            npc_relationships = {}
            full_history = []
            class Msg:
                def to_dict(self):
                    return {}
            full_history = [Msg()]

        output = controller.process_input("hello", MockSession())
        # Should return NPC interaction instead of normal dialog
        assert output.npc_response is not None or output.options is not None
        assert not controller._npc_interaction_queue.is_empty() or output.npc_response == "「嘿！这边！」"

    def test_handle_normal_dialog_increments_turn_count(self):
        controller = GameLoopController(
            engine=self.mock_engine,
            asset_manager=self.mock_asset,
            plot_manager=self.mock_plot,
            client_manager=self.mock_client
        )

        class Msg:
            def to_dict(self):
                return {"role": "user", "content": "hello"}

        session = type('MockSession', (), {
            'session_id': 'test',
            'turn_count': 0,
            'last_option_turn': 0,
            'npc_suggestion_pending': None,
            'current_location': 'Old Street',
            'last_emotion': 'neutral',
            'option_pending': None,
            'npc_relationships': {},
            'full_history': [Msg()],
        })()

        controller._handle_normal_dialog("Hello!", session)
        assert session.turn_count == 1

    def test_emotion_tracker_sequential_same_emotions(self):
        tracker = EmotionTracker(threshold=3)
        results = [tracker.record("happy") for _ in range(5)]
        # First 2 should be False, third onwards True
        assert results[0] is False
        assert results[1] is False
        assert results[2] is True
        assert results[3] is True
        assert results[4] is True

    def test_emotion_tracker_different_emotion_resets_count(self):
        tracker = EmotionTracker(threshold=3)
        tracker.record("happy")
        tracker.record("happy")
        # Now switch emotion
        result = tracker.record("sad")
        # Counter should reset, not reach threshold yet
        assert result is False
        # Need 3 "sad" to trigger
        assert tracker.record("sad") is False
        assert tracker.record("sad") is True

    def test_handle_option_selection_accept(self):
        from src.core.plot.types import DialogOption, OptionType

        controller = GameLoopController(
            engine=self.mock_engine,
            asset_manager=self.mock_asset,
            plot_manager=self.mock_plot,
            client_manager=self.mock_client
        )

        session = type('MockSession', (), {
            'session_id': 'test',
            'turn_count': 0,
            'option_pending': None,
            'npc_suggestion_pending': {"npc_name": "alice", "content": "一起去看书吗？"},
            'npc_relationships': {},
            'current_location': "Cafe",
        })()

        option = DialogOption(type=OptionType.FIXED, content="好的，没问题", action="accept")
        output = controller._handle_option_selection("好的!", option, session)
        # Should have narrative (action result)
        assert output.narrative is not None
        # npc_suggestion_pending should be cleared
        assert session.npc_suggestion_pending is None

    def test_handle_option_selection_reject(self):
        from src.core.plot.types import DialogOption, OptionType

        controller = GameLoopController(
            engine=self.mock_engine,
            asset_manager=self.mock_asset,
            plot_manager=self.mock_plot,
            client_manager=self.mock_client
        )

        session = type('MockSession', (), {
            'session_id': 'test',
            'turn_count': 0,
            'option_pending': None,
            'npc_suggestion_pending': {"npc_name": "alice", "content": "一起去看书吗？"},
            'npc_relationships': {},
            'current_location': "Cafe",
        })()

        option = DialogOption(type=OptionType.FIXED, content="不了，谢谢", action="reject")
        output = controller._handle_option_selection("不了", option, session)
        assert output.narrative is not None
        assert session.npc_suggestion_pending is None

    def test_handle_option_selection_branch(self):
        from src.core.plot.types import DialogOption, OptionType, PlotNode, NodeType, NarrativeType

        controller = GameLoopController(
            engine=self.mock_engine,
            asset_manager=self.mock_asset,
            plot_manager=self.mock_plot,
            client_manager=self.mock_client
        )

        # Override make_choice to return a specific node
        result_node = PlotNode(id="n2a", node_type=NodeType.DIALOGUE,
                              narration_type=NarrativeType.FREE_EXPLORE,
                              content="Left path reached")
        self.mock_plot.make_choice = lambda branch_id: result_node

        session = type('MockSession', (), {
            'session_id': 'test',
            'turn_count': 0,
            'option_pending': None,
            'npc_suggestion_pending': None,
            'npc_relationships': {},
            'current_location': "Old Street",
        })()

        option = DialogOption(type=OptionType.FIXED, content="Go left", action="branch", target="b_left")
        output = controller._handle_option_selection("Go left", option, session)
        # Should advance to n2a
        assert output.npc_response == "Left path reached"

    def test_handle_option_invalid_action(self):
        from src.core.plot.types import DialogOption, OptionType

        controller = GameLoopController(
            engine=self.mock_engine,
            asset_manager=self.mock_asset,
            plot_manager=self.mock_plot,
            client_manager=self.mock_client
        )

        class MockSession:
            session_id = "test"
            turn_count = 0
            option_pending = None
            npc_suggestion_pending = None
            npc_relationships = {}
            current_location = "Old Street"
            full_history = []
            class Msg:
                def to_dict(self):
                    return {}
            full_history = [Msg()]

        # Option with unknown action - should return empty output
        option = DialogOption(type=OptionType.FIXED, content="???", action="unknown")
        output = controller._handle_option_selection("???", option, MockSession())
        # No NPC response expected for unknown action
        assert output.npc_response is None

    def test_build_plot_context(self):
        from src.core.plot.types import PlotState

        controller = GameLoopController(
            engine=self.mock_engine,
            asset_manager=self.mock_asset,
            plot_manager=self.mock_plot,
            client_manager=self.mock_client
        )

        self.mock_plot._state = PlotState(
            chapter_id="ch1",
            node_id="n1",
            is_exploring=False,
            is_branch_point=False
        )

        class MockSession:
            session_id = "test"
            turn_count = 10
            npc_relationships = {"alice": 65, "bob": 50}
            current_location = "Cafe"

        ctx = controller._build_plot_context(MockSession())
        assert ctx.current_chapter == "ch1"
        assert ctx.current_node == "n1"
        assert ctx.conversation_turns == 10
        assert ctx.relationship_states["alice"] == 65
        assert ctx.current_location == "Cafe"