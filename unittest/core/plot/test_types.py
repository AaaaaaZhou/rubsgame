"""
剧情系统数据类型测试
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import pytest
from src.core.plot.types import (
    NodeType, TriggerType, NarrativeType, Condition, Branch, Trigger,
    PlotNode, Chapter, PlotState, PlotContext,
    InteractionTrigger, NPCInteraction, InteractionQueue,
    OptionType, OptionMode, DialogOption, OptionOutput, NarrativeOutput
)


class TestNodeType:
    def test_all_node_types_exist(self):
        assert NodeType.DIALOGUE.value == "dialogue"
        assert NodeType.CHOICE.value == "choice"
        assert NodeType.NARRATION_ONLY.value == "narration_only"
        assert NodeType.BRANCH.value == "branch"
        assert NodeType.NPC_INTERACT.value == "npc_interact"


class TestNarrativeType:
    def test_all_narrative_types_exist(self):
        assert NarrativeType.SCENE_ENTER.value == "scene_enter"
        assert NarrativeType.SCENE_EXIT.value == "scene_exit"
        assert NarrativeType.EMOTION_BUILD.value == "emotion_build"
        assert NarrativeType.TRANSITION.value == "transition"
        assert NarrativeType.ACTION_RESULT.value == "action_result"
        assert NarrativeType.CHAPTER_START.value == "chapter_start"
        assert NarrativeType.CHAPTER_END.value == "chapter_end"
        assert NarrativeType.FREE_EXPLORE.value == "free_explore"
        assert NarrativeType.INNER_MONOLOGUE.value == "inner_monologue"


class TestCondition:
    def test_condition_defaults(self):
        c = Condition()
        assert c.relationship_min is None
        assert c.relationship_max is None
        assert c.has_item is None
        assert c.flag is None

    def test_condition_full(self):
        c = Condition(relationship_min=50, relationship_max=80, has_item="key", flag="visited")
        assert c.relationship_min == 50
        assert c.relationship_max == 80
        assert c.has_item == "key"
        assert c.flag == "visited"


class TestBranch:
    def test_branch_basic(self):
        b = Branch(id="b1", label="选择A", next_node="n2")
        assert b.id == "b1"
        assert b.label == "选择A"
        assert b.condition is None
        assert b.next_node == "n2"


class TestPlotNode:
    def test_plot_node_defaults(self):
        node = PlotNode(id="n1")
        assert node.id == "n1"
        assert node.node_type == NodeType.DIALOGUE
        assert node.npc_name is None
        assert node.content == ""
        assert node.next is None
        assert node.branches is None
        assert node.triggers == []
        assert node.narration_type == NarrativeType.FREE_EXPLORE

    def test_plot_node_full(self):
        branch = Branch(id="b1", label="选项1", next_node="n2")
        node = PlotNode(
            id="n1",
            node_type=NodeType.BRANCH,
            npc_name="alice",
            content="选择你的行动",
            next=None,
            branches=[branch],
            triggers=[],
            narration_type=NarrativeType.FREE_EXPLORE
        )
        assert node.id == "n1"
        assert node.node_type == NodeType.BRANCH
        assert node.npc_name == "alice"
        assert len(node.branches) == 1


class TestChapter:
    def test_chapter_empty(self):
        ch = Chapter(id="ch1", name="第一章")
        assert ch.id == "ch1"
        assert ch.name == "第一章"
        assert ch.nodes == []
        assert ch.current_node_index == 0

    def test_chapter_with_nodes(self):
        ch = Chapter(id="ch1", name="第一章")
        ch.nodes.append(PlotNode(id="n1"))
        ch.nodes.append(PlotNode(id="n2"))
        assert len(ch.nodes) == 2


class TestPlotState:
    def test_plot_state_defaults(self):
        ps = PlotState()
        assert ps.chapter_id == ""
        assert ps.node_id == ""
        assert ps.is_exploring is False
        assert ps.is_branch_point is False
        assert ps.queued_narrative is None


class TestPlotContext:
    def test_plot_context_defaults(self):
        pc = PlotContext()
        assert pc.current_chapter == ""
        assert pc.current_node == ""
        assert pc.current_location == ""
        assert pc.conversation_turns == 0
        assert pc.relationship_states == {}

    def test_plot_context_full(self):
        pc = PlotContext(
            current_chapter="ch1",
            current_node="n1",
            current_location="老街",
            conversation_turns=5,
            relationship_states={"alice": 60, "bob": 50}
        )
        assert pc.current_chapter == "ch1"
        assert pc.relationship_states["alice"] == 60


class TestNPCInteraction:
    def test_npc_interaction_defaults(self):
        ni = NPCInteraction(
            trigger=InteractionTrigger.LOCATION_CHANGE,
            npc_name="alice"
        )
        assert ni.trigger == InteractionTrigger.LOCATION_CHANGE
        assert ni.npc_name == "alice"
        assert ni.priority == 5
        assert ni.content is None
        assert ni.cooldown_turns == 10
        assert ni.last_triggered_turn == 0


class TestInteractionQueue:
    def test_queue_empty(self):
        q = InteractionQueue()
        assert q.is_empty() is True
        assert q.pop() is None
        assert q.peek() is None

    def test_queue_priority_order(self):
        q = InteractionQueue()
        q.interactions.append(
            NPCInteraction(trigger=InteractionTrigger.LOCATION_CHANGE, npc_name="bob", priority=3)
        )
        q.interactions.append(
            NPCInteraction(trigger=InteractionTrigger.STORY_NODE, npc_name="alice", priority=10)
        )
        # STORY_NODE has higher priority, should pop first
        first = q.pop()
        assert first.npc_name == "alice"

    def test_queue_peek(self):
        q = InteractionQueue()
        q.interactions.append(
            NPCInteraction(trigger=InteractionTrigger.LOCATION_CHANGE, npc_name="bob", priority=5)
        )
        peeked = q.peek()
        assert peeked.npc_name == "bob"
        # peek should not remove
        assert q.is_empty() is False


class TestDialogOption:
    def test_dialog_option(self):
        opt = DialogOption(type=OptionType.FIXED, content="进店坐下", action="enter_cafe")
        assert opt.type == OptionType.FIXED
        assert opt.content == "进店坐下"
        assert opt.action == "enter_cafe"
        assert opt.target is None


class TestOptionOutput:
    def test_option_output(self):
        opts = [DialogOption(type=OptionType.FIXED, content="选项1")]
        out = OptionOutput(options=opts, mode=OptionMode.FORCE_CHOICE)
        assert len(out.options) == 1
        assert out.mode == OptionMode.FORCE_CHOICE
        assert out.expires_at is None


class TestNarrativeOutput:
    def test_narrative_output(self):
        no = NarrativeOutput(
            text="阳光洒在老街的石板路上",
            context=NarrativeType.SCENE_ENTER,
            duration_hint="short",
            skip_allowed=True
        )
        assert no.text == "阳光洒在老街的石板路上"
        assert no.context == NarrativeType.SCENE_ENTER
        assert no.duration_hint == "short"
        assert no.skip_allowed is True