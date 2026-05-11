# Refiner - PersonaExtractor 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Stage 2b，将 AnalysisResult 中的角色转换为 NPCProfile

**Architecture:** 与现有 NPCLoader 输出同规格，依赖 Persona、PersonaEmotionConfig、NPCProfile、NPCRelationship、NPCMemory

**Tech Stack:** Persona, NPCProfile, NPCRelationship, NPCMemory from src/core/

---

## File Structure

```
refiner/
├── extractors/
│   └── persona_extractor.py  (Create)
```

---

## Task 1: 实现 PersonaExtractor

**Files:**
- Create: `refiner/extractors/persona_extractor.py`
- Test: `unittest/refiner/test_persona_extractor.py`

- [ ] **Step 1: 编写测试文件**

```python
# unittest/refiner/test_persona_extractor.py
import pytest
from unittest.mock import MagicMock
from refiner.extractors.persona_extractor import PersonaExtractor
from refiner.types import AnalysisResult, CharacterInfo


def _make_analysis_result():
    """创建测试用 AnalysisResult"""
    return AnalysisResult(
        world_name="清溪镇",
        characters=[
            CharacterInfo(
                name="Alice",
                gender="女",
                age="17",
                identity="高中学生",
                personality_traits=["温和", "内敛", "善良"],
                speech_features=["说话轻柔", "较少使用网络用语"],
                background_summary="在小镇长大，对大城市充满向往"
            ),
            CharacterInfo(
                name="Bob",
                gender="男",
                age="18",
                identity="高中学生",
                personality_traits=["外向", "开朗", "爱冒险"],
                speech_features=["说话直接", "爱开玩笑"],
                background_summary="喜欢户外活动，是镇上的本地人"
            ),
        ],
        locations=[],
        events=[],
        relationships=[
            RelationshipInfo(subject="Alice", object="Bob", relation_type="friend", affinity=30, trust=40, description="同学")
        ]
    )


def test_persona_extractor_initialization():
    """测试 PersonaExtractor 初始化"""
    mock_client_mgr = MagicMock()
    extractor = PersonaExtractor(mock_client_mgr)
    assert extractor._client_mgr is mock_client_mgr


def test_extract_single_character():
    """测试提取单个角色"""
    mock_client_mgr = MagicMock()
    extractor = PersonaExtractor(mock_client_mgr)

    char_info = CharacterInfo(
        name="Alice",
        gender="女",
        age="17",
        identity="高中学生",
        personality_traits=["温和", "善良"],
        speech_features=["说话轻柔"],
        background_summary="在小镇长大"
    )

    profile = extractor.extract(char_info)

    assert profile.persona.name == "Alice"
    assert profile.persona.emotion_config.default_emotion == "neutral"


def test_extract_multiple_characters():
    """测试提取多个角色"""
    mock_client_mgr = MagicMock()
    extractor = PersonaExtractor(mock_client_mgr)

    analysis = _make_analysis_result()
    profiles = extractor.extract_all(analysis)

    assert len(profiles) == 2
    names = {p.persona.name for p in profiles}
    assert "Alice" in names
    assert "Bob" in names


def test_persona_fields_mapped():
    """测试 persona.yaml 字段正确映射"""
    mock_client_mgr = MagicMock()
    extractor = PersonaExtractor(mock_client_mgr)

    char_info = CharacterInfo(
        name="Alice",
        gender="女",
        age="17",
        identity="高三学生",
        personality_traits=["温和", "内敛", "善良"],
        speech_features=["轻柔", "腼腆"],
        background_summary="向往沿海大城市"
    )

    profile = extractor.extract(char_info)
    persona = profile.persona

    # 验证 persona.yaml 关键字段
    assert persona.raw_data.get("name") == "Alice"
    assert persona.raw_data.get("gender") == "女"
    assert persona.raw_data.get("age") == 17
    assert persona.raw_data.get("identity") == "高三学生"
    assert "温和" in persona.raw_data.get("personality", {}).get("core_traits", [])
    assert persona.raw_data.get("speech_style", {}).get("tone") == "轻柔"


def test_npc_profile_has_relationships():
    """测试 NPCProfile 包含 relationships 字段"""
    mock_client_mgr = MagicMock()
    extractor = PersonaExtractor(mock_client_mgr)

    analysis = _make_analysis_result()
    profiles = extractor.extract_all(analysis)

    # 至少一个 profile 应该有 relationships
    has_rels = any(len(p.relationships) > 0 for p in profiles)
    assert has_rels


def test_npc_profile_empty_characters():
    """测试空角色列表"""
    mock_client_mgr = MagicMock()
    extractor = PersonaExtractor(mock_client_mgr)

    analysis = AnalysisResult(world_name="test", characters=[], locations=[], events=[], relationships=[])
    profiles = extractor.extract_all(analysis)

    assert len(profiles) == 0


def test_relationship_info_import():
    """测试 RelationshipInfo 可导入"""
    from refiner.types import RelationshipInfo
    r = RelationshipInfo(subject="A", object="B", relation_type="friend")
    assert r.relation_type == "friend"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest unittest/refiner/test_persona_extractor.py -v`
Expected: FAIL (import error - module not found)

- [ ] **Step 3: 编写 PersonaExtractor 实现**

```python
"""
Stage 2b: PersonaExtractor
将 CharacterInfo 转换为 NPCProfile
"""
import logging
from typing import List, Optional

from ...clients.manager import ClientManager
from ...src.core.persona import Persona, PersonaEmotionConfig
from ...src.core.npc import NPCProfile, NPCRelationship, NPCMemory
from ..types import AnalysisResult, CharacterInfo, RelationshipInfo

_logger = logging.getLogger("refiner.persona_extractor")


class PersonaExtractor:
    """NPC 档案提取器 - Stage 2b"""

    def __init__(
        self,
        client_manager: ClientManager,
        model_name: Optional[str] = None
    ):
        self._client_mgr = client_manager
        self._model_name = model_name

    def extract(self, char_info: CharacterInfo) -> NPCProfile:
        """将单个 CharacterInfo 转换为 NPCProfile

        Args:
            char_info: 角色信息

        Returns:
            NPCProfile 对象
        """
        persona = self._build_persona(char_info)

        profile = NPCProfile(
            persona=persona,
            relationships={},
            private_memories=[]
        )

        _logger.info(f"Extracted NPCProfile: {char_info.name}")
        return profile

    def extract_all(self, analysis: AnalysisResult) -> List[NPCProfile]:
        """从 AnalysisResult 提取所有角色

        Args:
            analysis: TextAnalyzer 输出

        Returns:
            NPCProfile 列表
        """
        profiles = []

        for char_info in analysis.characters:
            if not char_info.name:
                continue
            profile = self.extract(char_info)
            profiles.append(profile)

        # 处理关系
        self._apply_relationships(profiles, analysis.relationships)

        _logger.info(f"Extracted {len(profiles)} NPCProfiles")
        return profiles

    def _build_persona(self, char_info: CharacterInfo) -> Persona:
        """构建 Persona 对象"""
        # 构建 persona.yaml 格式的 raw_data
        raw_data = self._build_persona_yaml_data(char_info)

        # 构建 system_prompt
        system_prompt = self._build_system_prompt(char_info)

        # 构建 emotion_config
        emotion_config = PersonaEmotionConfig(
            default_emotion="neutral",
            allowed_emotions=["happy", "sad", "neutral", "surprised", "angry"],
            blocked_emotions=[],
            expression_intensity=0.7,
            material_package="kaomoji_cute"
        )

        return Persona(
            name=char_info.name,
            system_prompt=system_prompt,
            emotion_config=emotion_config,
            raw_data=raw_data
        )

    def _build_persona_yaml_data(self, char_info: CharacterInfo) -> dict:
        """构建符合 persona.yaml 格式的数据"""
        return {
            "name": char_info.name,
            "gender": char_info.gender,
            "age": char_info.age if char_info.age else None,
            "identity": char_info.identity,
            "basic_info": {
                "academic_performance": "未知",
                "residence": "本地",
                "family_background": "普通家庭"
            },
            "personality": {
                "core_traits": char_info.personality_traits[:5] if char_info.personality_traits else [],
                "preferences": {
                    "likes": [],
                    "dislikes": []
                }
            },
            "behaviors": {
                "conflict_response": {
                    "description": "面对冲突时的行为",
                    "好感度影响": -5
                },
                "social_interaction": {
                    "description": "社交行为特点",
                    "friendliness_range": [1, 10]
                }
            },
            "mood_system": {
                "baseline": 65,
                "factors": {
                    "positive": ["被尊重", "讨论喜欢的话题"],
                    "negative": ["被大声呵斥", "被迫社交"]
                }
            },
            "background": {
                "education": char_info.identity,
                "dreams": [],
                "limitations": []
            },
            "speech_style": {
                "tone": self._infer_tone(char_info.speech_features),
                "vocabulary": "日常",
                "features": char_info.speech_features[:3] if char_info.speech_features else []
            },
            "topics_of_interest": []
        }

    def _build_system_prompt(self, char_info: CharacterInfo) -> str:
        """构建系统提示词"""
        parts = [f"You are {char_info.name}"]

        if char_info.gender:
            parts.append(char_info.gender)
        if char_info.age:
            parts.append(f"{char_info.age} years old")
        if char_info.identity:
            parts.append(char_info.identity)

        if char_info.personality_traits:
            traits_str = ", ".join(char_info.personality_traits[:3])
            parts.append(f"\n## Personality\n{traits_str}")

        if char_info.background_summary:
            parts.append(f"\n## Background\n{char_info.background_summary}")

        if char_info.speech_features:
            features_str = ", ".join(char_info.speech_features[:2])
            parts.append(f"\n## Speech Style\n{features_str}")

        return "\n".join(parts)

    def _infer_tone(self, speech_features: List[str]) -> str:
        """从语言特征推断语气"""
        if not speech_features:
            return "温和"
        features_text = " ".join(speech_features).lower()

        if any(word in features_text for word in ["轻柔", "温柔", "腼腆", "害羞"]):
            return "轻柔温和"
        elif any(word in features_text for word in ["直接", "爽朗", "开朗"]):
            return "爽朗直接"
        elif any(word in features_text for word in ["严肃", "正经"]):
            return "严肃认真"
        else:
            return "温和"

    def _apply_relationships(
        self,
        profiles: List[NPCProfile],
        relationships: List[RelationshipInfo]
    ):
        """将关系应用到 NPCProfile"""
        profile_map = {p.persona.name: p for p in profiles}

        for rel in relationships:
            subject_profile = profile_map.get(rel.subject)
            if not subject_profile:
                continue

            npc_rel = NPCRelationship(
                subject_id=rel.subject,
                object_id=rel.object,
                relation_type=rel.relation_type,
                affinity=rel.affinity,
                trust=rel.trust,
                key_events=[rel.description] if rel.description else []
            )

            subject_profile.relationships[rel.object] = npc_rel
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest unittest/refiner/test_persona_extractor.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add refiner/extractors/persona_extractor.py unittest/refiner/test_persona_extractor.py
git commit -m "feat(refiner): add PersonaExtractor (Stage 2b)"
```