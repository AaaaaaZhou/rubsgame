"""
NPCInteractionManager tests
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import pytest
from src.core.plot.npc_interaction import NPCInteractionManager, QUEUE_PRIORITY
from src.core.plot.types import (
    InteractionTrigger, NPCInteraction, InteractionQueue,
    PlotContext, Condition
)


class MockPlotManager:
    def __init__(self):
        self.location_triggers = {}
        self.relation_triggers = {}


class MockAssetManager:
    pass


class TestQueuePriority:
    def test_story_node_has_highest_priority(self):
        assert QUEUE_PRIORITY[InteractionTrigger.STORY_NODE] == 10
        assert QUEUE_PRIORITY[InteractionTrigger.LOCATION_CHANGE] == 5
        assert QUEUE_PRIORITY[InteractionTrigger.RELATION_THRESHOLD] == 3
        assert QUEUE_PRIORITY[InteractionTrigger.STORY_NODE] > QUEUE_PRIORITY[InteractionTrigger.LOCATION_CHANGE]


class TestNPCInteractionManager:
    def setup_method(self):
        self.mock_asset = MockAssetManager()
        self.mock_plot = MockPlotManager()
        self.manager = NPCInteractionManager(
            self.mock_asset,
            self.mock_plot,
            default_cooldown=10
        )

    def test_register_location_trigger(self):
        self.manager.register_location_trigger(
            location="老街",
            npc_name="alice",
            content="「你也来老街了？」",
            priority=8,
            cooldown_turns=5
        )
        triggers = self.manager._location_triggers.get("老街", [])
        assert len(triggers) == 1
        assert triggers[0].npc_name == "alice"
        assert triggers[0].trigger == InteractionTrigger.LOCATION_CHANGE
        assert triggers[0].priority == 8
        assert triggers[0].cooldown_turns == 5

    def test_register_relation_trigger(self):
        self.manager.register_relation_trigger(
            npc_name="alice",
            condition=Condition(relationship_min=60),
            content="「今天心情不错。」",
            priority=5
        )
        triggers = self.manager._relation_triggers.get("alice", [])
        assert len(triggers) == 1
        assert triggers[0].npc_name == "alice"
        assert triggers[0].trigger == InteractionTrigger.RELATION_THRESHOLD
        assert triggers[0].condition.relationship_min == 60

    def test_register_story_trigger(self):
        self.manager.register_story_trigger(
            node_id="n_special",
            npc_name="alice",
            content="「找到你了！」",
            priority=10
        )
        assert self.manager._story_triggers["n_special"].npc_name == "alice"
        assert self.manager._story_triggers["n_special"].trigger == InteractionTrigger.STORY_NODE

    def test_check_location_triggers(self):
        self.manager.register_location_trigger(
            location="老街",
            npc_name="alice",
            priority=8,
            cooldown_turns=5
        )
        context = PlotContext(
            current_chapter="ch1",
            current_node="n1",
            current_location="老街",
            conversation_turns=0,
            relationship_states={}
        )
        queue = self.manager.check_and_queue_interactions(context)
        assert len(queue.interactions) == 1
        assert queue.interactions[0].npc_name == "alice"

    def test_check_relation_triggers(self):
        self.manager.register_relation_trigger(
            npc_name="alice",
            condition=Condition(relationship_min=60),
            priority=5
        )
        context = PlotContext(
            current_chapter="ch1",
            current_node="n1",
            current_location="老街",
            conversation_turns=0,
            relationship_states={"alice": 65}
        )
        queue = self.manager.check_and_queue_interactions(context)
        assert len(queue.interactions) == 1

    def test_relation_trigger_not_met(self):
        self.manager.register_relation_trigger(
            npc_name="alice",
            condition=Condition(relationship_min=60),
            priority=5
        )
        context = PlotContext(
            current_chapter="ch1",
            current_node="n1",
            current_location="老街",
            conversation_turns=0,
            relationship_states={"alice": 50}  # Below threshold
        )
        queue = self.manager.check_and_queue_interactions(context)
        assert len(queue.interactions) == 0

    def test_cooldown_blocks_trigger(self):
        self.manager.register_location_trigger(
            location="老街",
            npc_name="alice",
            priority=8,
            cooldown_turns=5
        )
        # Mark alice as having interacted recently
        self.manager.mark_interaction_done("alice", current_turn=3)

        context = PlotContext(
            current_chapter="ch1",
            current_node="n1",
            current_location="老街",
            conversation_turns=5,  # Only 2 turns since interaction (not >= 5 cooldown)
            relationship_states={}
        )
        queue = self.manager.check_and_queue_interactions(context)
        # Should be blocked by cooldown
        assert len(queue.interactions) == 0

    def test_cooldown_allows_after_cooldown_period(self):
        self.manager.register_location_trigger(
            location="老街",
            npc_name="alice",
            priority=8,
            cooldown_turns=5
        )
        self.manager.mark_interaction_done("alice", current_turn=3)

        context = PlotContext(
            current_chapter="ch1",
            current_node="n1",
            current_location="老街",
            conversation_turns=10,  # 7 turns since interaction (>= 5 cooldown)
            relationship_states={}
        )
        queue = self.manager.check_and_queue_interactions(context)
        assert len(queue.interactions) == 1

    def test_mark_interaction_done(self):
        self.manager.mark_interaction_done("alice", current_turn=5)
        assert self.manager._cooldown_records["alice"] == 5

    def test_priority_ordering_in_queue(self):
        # STORY_NODE (priority 10) should come before LOCATION_CHANGE (priority 5)
        self.manager._story_triggers["n1"] = NPCInteraction(
            trigger=InteractionTrigger.STORY_NODE,
            npc_name="alice",
            priority=10,
            cooldown_turns=100
        )
        self.manager._location_triggers["老街"] = [
            NPCInteraction(
                trigger=InteractionTrigger.LOCATION_CHANGE,
                npc_name="bob",
                priority=5,
                cooldown_turns=100
            )
        ]

        context = PlotContext(
            current_chapter="ch1",
            current_node="n1",
            current_location="老街",
            conversation_turns=0,
            relationship_states={}
        )
        queue = self.manager.check_and_queue_interactions(context)
        assert len(queue.interactions) == 2

        # Pop should return highest priority first
        first = queue.pop()
        assert first.npc_name == "alice"  # STORY_NODE has higher priority

    def test_multiple_triggers_same_location(self):
        self.manager.register_location_trigger(
            location="老街",
            npc_name="alice",
            priority=8
        )
        self.manager.register_location_trigger(
            location="老街",
            npc_name="bob",
            priority=7
        )
        context = PlotContext(
            current_chapter="ch1",
            current_node="n1",
            current_location="老街",
            conversation_turns=0,
            relationship_states={}
        )
        queue = self.manager.check_and_queue_interactions(context)
        assert len(queue.interactions) == 2

    def test_check_and_queue_interactions_empty(self):
        context = PlotContext(
            current_chapter="ch1",
            current_node="n1",
            current_location="未知地点",
            conversation_turns=0,
            relationship_states={}
        )
        queue = self.manager.check_and_queue_interactions(context)
        assert queue.is_empty() is True