"""
NPC 数据模型测试
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import pytest
import time
from src.core.npc import NPCRelationship, NPCMemory, NPCProfile
from src.core.persona import Persona, PersonaEmotionConfig


class TestNPCRelationship:
    """测试 NPCRelationship 类"""

    def test_creation(self):
        rel = NPCRelationship(
            subject_id="alice",
            object_id="player",
            relation_type="friend",
            affinity=75,
            trust=60,
            key_events=["一起完成班级任务"]
        )
        assert rel.subject_id == "alice"
        assert rel.object_id == "player"
        assert rel.relation_type == "friend"
        assert rel.affinity == 75
        assert rel.trust == 60
        assert len(rel.key_events) == 1

    def test_affinity_clamp(self):
        rel = NPCRelationship(
            subject_id="alice",
            object_id="player",
            relation_type="stranger",
            affinity=200
        )
        assert rel.affinity == 100

        rel2 = NPCRelationship(
            subject_id="alice",
            object_id="player",
            relation_type="stranger",
            affinity=-200
        )
        assert rel2.affinity == -100

    def test_trust_clamp(self):
        rel = NPCRelationship(
            subject_id="alice",
            object_id="player",
            relation_type="stranger",
            trust=150
        )
        assert rel.trust == 100

    def test_to_dict(self):
        rel = NPCRelationship(
            subject_id="alice",
            object_id="player",
            relation_type="rival",
            affinity=-20,
            trust=10,
            key_events=["发生过争执"]
        )
        data = rel.to_dict()
        assert data["subject_id"] == "alice"
        assert data["object_id"] == "player"
        assert data["relation_type"] == "rival"
        assert data["affinity"] == -20
        assert data["trust"] == 10
        assert "发生过争执" in data["key_events"]

    def test_from_dict(self):
        data = {
            "subject_id": "bob",
            "object_id": "player",
            "relation_type": "friend",
            "affinity": 80,
            "trust": 70,
            "key_events": ["一起旅行"]
        }
        rel = NPCRelationship.from_dict(data)
        assert rel.subject_id == "bob"
        assert rel.object_id == "player"
        assert rel.affinity == 80
        assert rel.trust == 70


class TestNPCMemory:
    """测试 NPCMemory 类"""

    def test_creation(self):
        mem = NPCMemory(
            memory_id="mem_001",
            owner_id="alice",
            content="玩家送了她一本书",
            memory_type="interaction",
            importance=8,
            emotional_valence=3,
            linked_to="player"
        )
        assert mem.memory_id == "mem_001"
        assert mem.owner_id == "alice"
        assert mem.content == "玩家送了她一本书"
        assert mem.memory_type == "interaction"
        assert mem.importance == 8
        assert mem.emotional_valence == 3
        assert mem.linked_to == "player"

    def test_importance_clamp(self):
        mem = NPCMemory(
            memory_id="mem_001",
            owner_id="alice",
            content="test",
            importance=15
        )
        assert mem.importance == 10

    def test_emotional_valence_clamp(self):
        mem = NPCMemory(
            memory_id="mem_001",
            owner_id="alice",
            content="test",
            emotional_valence=10
        )
        assert mem.emotional_valence == 5

    def test_to_dict(self):
        mem = NPCMemory(
            memory_id="mem_002",
            owner_id="bob",
            content="玩家帮助了他",
            memory_type="secret",
            importance=9,
            emotional_valence=4,
            linked_to="player"
        )
        data = mem.to_dict()
        assert data["memory_id"] == "mem_002"
        assert data["owner_id"] == "bob"
        assert data["memory_type"] == "secret"
        assert data["importance"] == 9
        assert data["emotional_valence"] == 4

    def test_from_dict(self):
        data = {
            "memory_id": "mem_003",
            "owner_id": "alice",
            "content": "一起看过夕阳",
            "memory_type": "observation",
            "importance": 6,
            "emotional_valence": 2,
            "linked_to": "player",
            "timestamp": 1234567890.0
        }
        mem = NPCMemory.from_dict(data)
        assert mem.memory_id == "mem_003"
        assert mem.content == "一起看过夕阳"
        assert mem.timestamp == 1234567890.0


class TestNPCProfile:
    """测试 NPCProfile 类"""

    def test_creation(self):
        persona = Persona(
            name="艾莉丝",
            system_prompt="You are Alice.",
            emotion_config=PersonaEmotionConfig()
        )
        rel = NPCRelationship(
            subject_id="alice",
            object_id="player",
            relation_type="friend",
            affinity=60,
            trust=50
        )
        mem = NPCMemory(
            memory_id="mem_001",
            owner_id="alice",
            content="test memory",
            memory_type="interaction"
        )
        profile = NPCProfile(
            persona=persona,
            relationships={"player": rel},
            private_memories=[mem]
        )
        assert profile.persona.name == "艾莉丝"
        assert len(profile.relationships) == 1
        assert len(profile.private_memories) == 1

    def test_get_relationship(self):
        persona = Persona(name="test", system_prompt="", emotion_config=PersonaEmotionConfig())
        rel = NPCRelationship(
            subject_id="test",
            object_id="player",
            relation_type="friend"
        )
        profile = NPCProfile(persona=persona, relationships={"player": rel})

        found = profile.get_relationship("player")
        assert found is rel
        assert found.relation_type == "friend"

        not_found = profile.get_relationship("nonexistent")
        assert not_found is None

    def test_get_memory_context(self):
        persona = Persona(name="test", system_prompt="", emotion_config=PersonaEmotionConfig())
        mem1 = NPCMemory(memory_id="m1", owner_id="test", content="重要记忆", memory_type="interaction", importance=9)
        mem2 = NPCMemory(memory_id="m2", owner_id="test", content="普通记忆", memory_type="observation", importance=3)
        profile = NPCProfile(persona=persona, private_memories=[mem1, mem2])

        ctx = profile.get_memory_context()
        assert "重要记忆" in ctx
        assert "普通记忆" in ctx
        # 按重要性排序，重要记忆在前
        assert ctx.index("重要记忆") < ctx.index("普通记忆")

    def test_get_memory_context_empty(self):
        persona = Persona(name="test", system_prompt="", emotion_config=PersonaEmotionConfig())
        profile = NPCProfile(persona=persona)
        assert profile.get_memory_context() == "No private memories."

    def test_get_relationship_context(self):
        persona = Persona(name="test", system_prompt="", emotion_config=PersonaEmotionConfig())
        rel1 = NPCRelationship(subject_id="test", object_id="player", relation_type="friend", affinity=80, trust=70)
        rel2 = NPCRelationship(subject_id="test", object_id="bob", relation_type="rival", affinity=-30, trust=20)
        profile = NPCProfile(persona=persona, relationships={"player": rel1, "bob": rel2})

        ctx = profile.get_relationship_context()
        assert "player" in ctx
        assert "friend" in ctx
        assert "80" in ctx
        assert "bob" in ctx
        assert "rival" in ctx

    def test_get_relationship_context_empty(self):
        persona = Persona(name="test", system_prompt="", emotion_config=PersonaEmotionConfig())
        profile = NPCProfile(persona=persona)
        assert profile.get_relationship_context() == "No relationship data."


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
