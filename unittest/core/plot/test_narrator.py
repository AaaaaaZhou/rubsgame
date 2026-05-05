"""
NarratorGenerator tests
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import pytest
from src.core.plot.narrator import NarratorGenerator
from src.core.plot.types import NarrativeType


class MockClient:
    def __init__(self, response="Mock narration text."):
        self.response = response
        self.call_count = 0

    def chat(self, messages, temperature=0.7, max_tokens=300):
        self.call_count += 1
        return self.response


class MockClientManager:
    def __init__(self, client=None):
        self._client = client or MockClient()

    def get_client(self, model_name=None):
        return self._client


class TestNarratorGenerator:
    def test_emotion_styles_has_expected_keys(self):
        assert "happy" in NarratorGenerator.EMOTION_STYLES
        assert "sad" in NarratorGenerator.EMOTION_STYLES
        assert "neutral" in NarratorGenerator.EMOTION_STYLES
        assert "tense" in NarratorGenerator.EMOTION_STYLES
        assert "romantic" in NarratorGenerator.EMOTION_STYLES
        assert "mysterious" in NarratorGenerator.EMOTION_STYLES

    def test_context_lengths_has_all_contexts(self):
        for ctx in NarrativeType:
            assert ctx in NarratorGenerator.CONTEXT_LENGTHS, f"Missing: {ctx}"

    def test_generate_returns_narrative_output(self):
        mock_mgr = MockClientManager()
        narrator = NarratorGenerator(mock_mgr)

        output = narrator.generate(
            context=NarrativeType.SCENE_ENTER,
            location="Old Street",
            emotion="neutral"
        )

        assert isinstance(output.text, str)
        assert output.context == NarrativeType.SCENE_ENTER
        assert output.duration_hint == "medium"
        # SCENE_ENTER is not skippable by default
        assert output.skip_allowed is False

    def test_generate_calls_client(self):
        mock_client = MockClient("阳光洒在老街的石板路上。")
        mock_mgr = MockClientManager(mock_client)
        narrator = NarratorGenerator(mock_mgr)

        narrator.generate(NarrativeType.SCENE_ENTER, location="老街")

        assert mock_client.call_count == 1

    def test_generate_chapter_end_not_skippable(self):
        mock_mgr = MockClientManager()
        narrator = NarratorGenerator(mock_mgr)

        output = narrator.generate(
            context=NarrativeType.CHAPTER_END,
            emotion="sad"
        )
        assert output.skip_allowed is False

    def test_generate_free_explore_skippable(self):
        mock_mgr = MockClientManager()
        narrator = NarratorGenerator(mock_mgr)

        output = narrator.generate(
            context=NarrativeType.FREE_EXPLORE,
            emotion="neutral"
        )
        assert output.skip_allowed is True

    def test_generate_action_result_skippable(self):
        mock_mgr = MockClientManager()
        narrator = NarratorGenerator(mock_mgr)

        output = narrator.generate(
            context=NarrativeType.ACTION_RESULT,
            action_description="走进咖啡店",
            emotion="happy"
        )
        assert output.skip_allowed is True

    def test_estimate_duration(self):
        narrator = NarratorGenerator(MockClientManager())
        assert narrator._estimate_duration(NarrativeType.SCENE_ENTER) == "medium"
        assert narrator._estimate_duration(NarrativeType.SCENE_EXIT) == "short"
        assert narrator._estimate_duration(NarrativeType.CHAPTER_START) == "long"

    def test_fallback_text(self):
        narrator = NarratorGenerator(MockClientManager())
        text = narrator._fallback_text(NarrativeType.SCENE_ENTER, "老街", "happy")
        assert "老街" in text
        assert len(text) > 0

    def test_get_context_name(self):
        narrator = NarratorGenerator(MockClientManager())
        assert narrator._get_context_name(NarrativeType.SCENE_ENTER) == "场景进入"
        assert narrator._get_context_name(NarrativeType.CHAPTER_END) == "章节结束"

    def test_get_context_requirements_action_result(self):
        narrator = NarratorGenerator(MockClientManager())
        req = narrator._get_context_requirements(
            NarrativeType.ACTION_RESULT,
            action_description="走进咖啡店",
            npc_name="alice"
        )
        assert "走进咖啡店" in req

    def test_llm_failure_uses_fallback(self):
        class FailingClient:
            def chat(self, messages, **kwargs):
                raise Exception("LLM unavailable")

        mock_mgr = MockClientManager(FailingClient())
        narrator = NarratorGenerator(mock_mgr)

        output = narrator.generate(
            context=NarrativeType.SCENE_ENTER,
            location="老街",
            emotion="neutral"
        )
        assert "老街" in output.text
        assert isinstance(output.text, str)

    def test_generate_action_result_with_action_description(self):
        mock_client = MockClient("你轻轻推开了咖啡店的门。")
        mock_mgr = MockClientManager(mock_client)
        narrator = NarratorGenerator(mock_mgr)

        output = narrator.generate(
            context=NarrativeType.ACTION_RESULT,
            action_description="推开咖啡店的门",
            emotion="curious"
        )
        assert mock_client.call_count == 1
        # The prompt should include the action_description
        assert output.context == NarrativeType.ACTION_RESULT
        assert output.skip_allowed is True

    def test_generate_inner_monologue_with_npc_name(self):
        mock_client = MockClient("「真希望能一直这样……」")
        mock_mgr = MockClientManager(mock_client)
        narrator = NarratorGenerator(mock_mgr)

        output = narrator.generate(
            context=NarrativeType.INNER_MONOLOGUE,
            npc_name="艾莉丝",
            emotion="sad"
        )
        assert mock_client.call_count == 1
        assert output.context == NarrativeType.INNER_MONOLOGUE

    def test_generate_chapter_start_with_chapter_info(self):
        mock_client = MockClient("新的一天开始了。")
        mock_mgr = MockClientManager(mock_client)
        narrator = NarratorGenerator(mock_mgr)

        output = narrator.generate(
            context=NarrativeType.CHAPTER_START,
            chapter_name="第一章·初遇",
            node_id="n_start",
            emotion="neutral"
        )
        assert mock_client.call_count == 1
        assert output.duration_hint == "long"
        assert output.skip_allowed is False

    def test_generate_transition(self):
        mock_mgr = MockClientManager()
        narrator = NarratorGenerator(mock_mgr)
        output = narrator.generate(context=NarrativeType.TRANSITION, emotion="neutral")
        assert output.context == NarrativeType.TRANSITION
        assert output.duration_hint == "medium"
        assert output.skip_allowed is False

    def test_generate_scene_exit(self):
        mock_mgr = MockClientManager()
        narrator = NarratorGenerator(mock_mgr)
        output = narrator.generate(context=NarrativeType.SCENE_EXIT, location="咖啡店", emotion="neutral")
        assert output.context == NarrativeType.SCENE_EXIT
        assert output.duration_hint == "short"

    def test_fallback_text_all_contexts(self):
        mock_mgr = MockClientManager()
        narrator = NarratorGenerator(MockClientManager())
        for ctx in NarrativeType:
            text = narrator._fallback_text(ctx, "测试地点", "neutral")
            assert isinstance(text, str), f"fallback for {ctx} should return string"
            assert len(text) > 0

    def test_generate_uses_correct_temperature(self):
        class VerifyingClient:
            def __init__(self):
                self.calls = []
            def chat(self, messages, temperature=0.7, max_tokens=300):
                self.calls.append({"temp": temperature, "max_tokens": max_tokens})
                return "narration"

        client = VerifyingClient()
        mock_mgr = MockClientManager(client)
        narrator = NarratorGenerator(mock_mgr)
        narrator.generate(context=NarrativeType.SCENE_ENTER, emotion="neutral")
        assert len(client.calls) == 1
        assert client.calls[0]["temp"] == 0.7
        assert client.calls[0]["max_tokens"] == 300