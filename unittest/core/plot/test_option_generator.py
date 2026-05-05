"""
OptionGenerator tests
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import pytest
from src.core.plot.option_generator import OptionGenerator
from src.core.plot.types import OptionType, OptionMode, DialogOption


class MockClient:
    def __init__(self, response="选项一 | 选项二 | 选项三"):
        self.response = response
        self.call_count = 0

    def chat(self, messages, temperature=0.9, max_tokens=150):
        self.call_count += 1
        return self.response


class MockClientManager:
    def __init__(self, client=None):
        self._client = client or MockClient()

    def get_client(self, model_name=None):
        return self._client


class TestOptionGenerator:
    def test_should_generate_option_normal_mode(self):
        mock_mgr = MockClientManager()
        gen = OptionGenerator(mock_mgr, option_interval_min=3, option_interval_max=5)

        # First check should set interval
        result = gen.should_generate_option(
            conversation_turns=0,
            last_option_turn=0,
            npc_suggestion_pending=False,
            is_branch_point=False
        )
        # Turn 0, next option at 3-5, should not trigger
        assert result is False

        # At turn 5, should trigger
        result = gen.should_generate_option(
            conversation_turns=5,
            last_option_turn=0,
            npc_suggestion_pending=False,
            is_branch_point=False
        )
        assert result is True

    def test_should_not_generate_at_branch_point(self):
        mock_mgr = MockClientManager()
        gen = OptionGenerator(mock_mgr)

        result = gen.should_generate_option(
            conversation_turns=10,
            last_option_turn=0,
            npc_suggestion_pending=False,
            is_branch_point=True
        )
        assert result is False

    def test_should_not_generate_when_npc_suggestion_pending(self):
        mock_mgr = MockClientManager()
        gen = OptionGenerator(mock_mgr)

        result = gen.should_generate_option(
            conversation_turns=10,
            last_option_turn=0,
            npc_suggestion_pending=True,
            is_branch_point=False
        )
        assert result is False

    def test_generate_npc_suggestion_options(self):
        mock_mgr = MockClientManager()
        gen = OptionGenerator(mock_mgr)

        output = gen.generate_npc_suggestion_options()
        assert output.mode == OptionMode.FORCE_CHOICE
        assert len(output.options) == 3
        assert output.options[0].action == "accept"
        assert output.options[1].action == "reject"
        assert output.options[2].type == OptionType.FREE_INPUT

    def test_generate_travel_options(self):
        mock_mgr = MockClientManager()
        gen = OptionGenerator(mock_mgr)

        output = gen.generate_travel_options(
            available_locations=["Old Street", "River", "Cafe"],
            current_location="Old Street"
        )
        assert output.mode == OptionMode.TRAVEL
        assert len(output.options) == 2  # Current location excluded
        assert all(opt.type == OptionType.TRAVEL for opt in output.options)

    def test_generate_travel_options_excludes_current(self):
        mock_mgr = MockClientManager()
        gen = OptionGenerator(mock_mgr)

        output = gen.generate_travel_options(
            available_locations=["Old Street", "River"],
            current_location="Old Street"
        )
        locations = [opt.target for opt in output.options]
        assert "Old Street" not in locations
        assert "River" in locations

    def test_generate_branch_options(self):
        from src.core.plot.types import Branch
        mock_mgr = MockClientManager()
        gen = OptionGenerator(mock_mgr)

        branches = [
            Branch(id="b1", label="Go left", next_node="n_left"),
            Branch(id="b2", label="Go right", next_node="n_right"),
        ]
        output = gen.generate_branch_options(branches, include_free_input=True)

        assert output.mode == OptionMode.FORCE_CHOICE
        assert len(output.options) == 3  # 2 branches + free input
        assert output.options[0].content == "Go left"
        assert output.options[1].content == "Go right"
        assert output.options[2].type == OptionType.FREE_INPUT

    def test_generate_branch_options_no_free_input(self):
        from src.core.plot.types import Branch
        mock_mgr = MockClientManager()
        gen = OptionGenerator(mock_mgr)

        branches = [Branch(id="b1", label="Option A", next_node="n1")]
        output = gen.generate_branch_options(branches, include_free_input=False)

        assert len(output.options) == 1
        assert output.options[0].type == OptionType.FIXED

    def test_reset_interval(self):
        mock_mgr = MockClientManager()
        gen = OptionGenerator(mock_mgr)

        gen.should_generate_option(10, 0, False, False)
        assert gen._next_option_turn is not None

        gen.reset_interval()
        assert gen._next_option_turn is None

    def test_parse_options_response(self):
        mock_mgr = MockClientManager()
        gen = OptionGenerator(mock_mgr)

        response = "选项一 | 选项二 | 选项三"
        options = gen._parse_options_response(response)

        assert len(options) == 3
        assert options[0].content == "选项一"
        assert options[1].content == "选项二"
        assert all(opt.type == OptionType.FIXED for opt in options)

    def test_parse_options_empty_response(self):
        mock_mgr = MockClientManager(MockClient(""))
        gen = OptionGenerator(mock_mgr)

        options = gen._parse_options_response("")
        assert len(options) == 0

    def test_format_chat_history(self):
        mock_mgr = MockClientManager()
        gen = OptionGenerator(mock_mgr)

        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        result = gen._format_chat_history(history)
        assert "玩家" in result
        assert "NPC" in result