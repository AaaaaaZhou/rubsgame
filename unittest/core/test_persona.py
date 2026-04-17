"""
人设数据模型测试
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import pytest
from core.persona import PersonaEmotionConfig, Persona


class TestPersonaEmotionConfig:
    """测试PersonaEmotionConfig类"""
    
    def test_emotion_config_creation(self):
        """测试情绪配置创建"""
        config = PersonaEmotionConfig(
            default_emotion="happy",
            allowed_emotions=["happy", "sad", "neutral"],
            blocked_emotions=["angry"],
            expression_intensity=0.8,
            material_package="kaomoji_cute"
        )
        
        assert config.default_emotion == "happy"
        assert "happy" in config.allowed_emotions
        assert "angry" in config.blocked_emotions
        assert config.expression_intensity == 0.8
        assert config.material_package == "kaomoji_cute"
    
    def test_emotion_config_defaults(self):
        """测试情绪配置默认值"""
        config = PersonaEmotionConfig()
        
        assert config.default_emotion == "neutral"
        assert set(config.allowed_emotions) == {"happy", "sad", "neutral"}
        assert config.blocked_emotions == []
        assert config.expression_intensity == 0.7
        assert config.material_package == "kaomoji_cute"
    
    def test_emotion_config_validation(self):
        """测试情绪配置验证"""
        # 测试无效强度值
        with pytest.raises(ValueError):
            PersonaEmotionConfig(expression_intensity=1.5)
        
        with pytest.raises(ValueError):
            PersonaEmotionConfig(expression_intensity=-0.5)
        
        # 测试默认情绪在禁止列表中
        with pytest.raises(ValueError):
            PersonaEmotionConfig(default_emotion="angry", blocked_emotions=["angry"])
    
    def test_emotion_config_post_init(self):
        """测试__post_init__方法"""
        # 测试默认情绪自动添加到允许列表
        config = PersonaEmotionConfig(default_emotion="surprised")
        assert "surprised" in config.allowed_emotions
        
        # 测试当默认情绪已在允许列表中时不会重复添加
        config = PersonaEmotionConfig(default_emotion="happy", allowed_emotions=["happy", "sad"])
        assert config.allowed_emotions.count("happy") == 1
    
    def test_is_emotion_allowed(self):
        """测试情绪是否允许"""
        # 注意：由于__post_init__会自动将默认情绪添加到允许列表，
        # 所以我们需要将默认情绪设置为已在允许列表中的情绪
        config = PersonaEmotionConfig(
            default_emotion="happy",  # 在允许列表中
            allowed_emotions=["happy", "sad"],
            blocked_emotions=["angry"]
        )
        
        assert config.is_emotion_allowed("happy") is True
        assert config.is_emotion_allowed("sad") is True
        assert config.is_emotion_allowed("angry") is False
        assert config.is_emotion_allowed("neutral") is False  # 不在允许列表中
        
        # 测试默认行为：当allowed_emotions为空时，__post_init__会自动添加默认情绪
        config = PersonaEmotionConfig(default_emotion="happy", allowed_emotions=[], blocked_emotions=["angry"])
        # allowed_emotions 现在应该是 ["happy"]
        assert config.is_emotion_allowed("happy") is True
        assert config.is_emotion_allowed("sad") is False  # 不在允许列表中
        assert config.is_emotion_allowed("angry") is False  # 在禁止列表中
    
    def test_filter_emotions(self):
        """测试情绪过滤"""
        config = PersonaEmotionConfig(
            allowed_emotions=["happy", "sad", "neutral"],
            blocked_emotions=["angry"]
        )
        
        emotions = ["happy", "sad", "angry", "neutral", "surprised"]
        filtered = config.filter_emotions(emotions)
        
        assert set(filtered) == {"happy", "sad", "neutral"}
        assert "angry" not in filtered
        assert "surprised" not in filtered
    
    def test_emotion_config_to_dict(self):
        """测试情绪配置序列化"""
        config = PersonaEmotionConfig(
            default_emotion="happy",
            allowed_emotions=["happy", "sad"],
            blocked_emotions=["angry"],
            expression_intensity=0.9,
            material_package="emoji_default"
        )
        
        data = config.to_dict()
        
        assert data["default_emotion"] == "happy"
        assert data["allowed_emotions"] == ["happy", "sad"]
        assert data["blocked_emotions"] == ["angry"]
        assert data["expression_intensity"] == 0.9
        assert data["material_package"] == "emoji_default"
    
    def test_emotion_config_from_dict(self):
        """测试情绪配置反序列化"""
        original = PersonaEmotionConfig(
            default_emotion="sad",
            allowed_emotions=["sad", "neutral"],
            blocked_emotions=["excited"],
            expression_intensity=0.5,
            material_package="kaomoji_serious"
        )
        
        data = original.to_dict()
        restored = PersonaEmotionConfig.from_dict(data)
        
        assert restored.default_emotion == original.default_emotion
        assert restored.allowed_emotions == original.allowed_emotions
        assert restored.blocked_emotions == original.blocked_emotions
        assert restored.expression_intensity == original.expression_intensity
        assert restored.material_package == original.material_package


class TestPersona:
    """测试Persona类"""
    
    def test_persona_creation(self):
        """测试人设创建"""
        emotion_config = PersonaEmotionConfig(default_emotion="happy")
        
        persona = Persona(
            name="Alice",
            system_prompt="You are Alice, a friendly assistant.",
            emotion_config=emotion_config
        )
        
        assert persona.name == "Alice"
        assert persona.system_prompt == "You are Alice, a friendly assistant."
        assert persona.emotion_config == emotion_config
        assert persona.raw_data == {}
    
    def test_create_from_yaml_data(self):
        """测试从YAML数据创建人设"""
        yaml_data = {
            "name": "Bob",
            "gender": "male",
            "age": 30,
            "identity": "shopkeeper",
            "background": {
                "education": "Trade school",
                "dreams": ["Own a chain of stores"]
            },
            "personality": {
                "core_traits": ["friendly", "hardworking"]
            },
            "emotion": {
                "default": "neutral",
                "allowed": ["happy", "neutral", "surprised"],
                "blocked": ["angry"],
                "intensity": 0.6,
                "material_package": "kaomoji_cute"
            }
        }
        
        persona = Persona.create_from_yaml_data(yaml_data)
        
        assert persona.name == "Bob"
        assert "Bob" in persona.system_prompt
        assert "male" in persona.system_prompt
        assert "shopkeeper" in persona.system_prompt
        assert "Trade school" in persona.system_prompt
        
        assert persona.emotion_config.default_emotion == "neutral"
        assert set(persona.emotion_config.allowed_emotions) == {"happy", "neutral", "surprised"}
        assert persona.emotion_config.blocked_emotions == ["angry"]
        assert persona.emotion_config.expression_intensity == 0.6
        assert persona.emotion_config.material_package == "kaomoji_cute"
        
        assert persona.raw_data == yaml_data
    
    def test_create_from_minimal_yaml_data(self):
        """测试从最小YAML数据创建人设"""
        yaml_data = {"name": "Charlie"}
        
        persona = Persona.create_from_yaml_data(yaml_data)
        
        assert persona.name == "Charlie"
        assert "Charlie" in persona.system_prompt
        assert persona.emotion_config.default_emotion == "neutral"  # 默认值
    
    def test_build_system_prompt(self):
        """测试系统提示词构建"""
        yaml_data = {
            "name": "David",
            "gender": "male",
            "age": 25,
            "identity": "knight",
            "background": "A knight from the northern kingdom.",
            "personality": {
                "core_traits": ["brave", "loyal"]
            }
        }
        
        prompt = Persona._build_system_prompt(yaml_data)
        
        assert "David" in prompt
        assert "male" in prompt
        assert "25" in prompt
        assert "knight" in prompt
        assert "northern kingdom" in prompt
        assert "brave" in prompt or "loyal" in prompt
    
    def test_create_emotion_config(self):
        """测试情绪配置创建"""
        yaml_data = {
            "emotion": {
                "default": "happy",
                "allowed": ["happy", "excited"],
                "blocked": ["sad"],
                "intensity": 0.8,
                "material_package": "emoji_default"
            }
        }
        
        config = Persona._create_emotion_config(yaml_data)
        
        assert config.default_emotion == "happy"
        assert set(config.allowed_emotions) == {"happy", "excited"}
        assert config.blocked_emotions == ["sad"]
        assert config.expression_intensity == 0.8
        assert config.material_package == "emoji_default"
    
    def test_create_emotion_config_defaults(self):
        """测试情绪配置默认值"""
        yaml_data = {}  # 没有emotion字段
        
        config = Persona._create_emotion_config(yaml_data)
        
        assert config.default_emotion == "neutral"
        assert set(config.allowed_emotions) == {"happy", "sad", "neutral"}
        assert config.blocked_emotions == []
        assert config.expression_intensity == 0.7
        assert config.material_package == "kaomoji_cute"
    
    def test_get_system_context(self):
        """测试获取系统上下文"""
        persona = Persona(
            name="Eve",
            system_prompt="You are Eve.",
            emotion_config=PersonaEmotionConfig()
        )
        
        assert persona.get_system_context() == "You are Eve."
    
    def test_update_emotion_config(self):
        """测试更新情绪配置"""
        persona = Persona(
            name="Frank",
            system_prompt="You are Frank.",
            emotion_config=PersonaEmotionConfig()
        )
        
        persona.update_emotion_config(
            default_emotion="excited",
            expression_intensity=0.9
        )
        
        assert persona.emotion_config.default_emotion == "excited"
        assert persona.emotion_config.expression_intensity == 0.9
        assert "excited" in persona.emotion_config.allowed_emotions
    
    def test_persona_to_dict(self):
        """测试人设序列化"""
        emotion_config = PersonaEmotionConfig(default_emotion="happy")
        
        persona = Persona(
            name="Grace",
            system_prompt="You are Grace.",
            emotion_config=emotion_config,
            raw_data={"test": "data"}
        )
        
        data = persona.to_dict()
        
        assert data["name"] == "Grace"
        assert data["system_prompt"] == "You are Grace."
        assert data["emotion_config"]["default_emotion"] == "happy"
        assert data["raw_data"]["test"] == "data"
    
    def test_persona_from_dict(self):
        """测试人设反序列化"""
        original = Persona(
            name="Henry",
            system_prompt="You are Henry.",
            emotion_config=PersonaEmotionConfig(default_emotion="sad"),
            raw_data={"original": True}
        )
        
        data = original.to_dict()
        restored = Persona.from_dict(data)
        
        assert restored.name == original.name
        assert restored.system_prompt == original.system_prompt
        assert restored.emotion_config.default_emotion == original.emotion_config.default_emotion
        assert restored.raw_data == original.raw_data
    
    def test_persona_str_repr(self):
        """测试人设字符串表示"""
        persona = Persona(
            name="Ivy",
            system_prompt="You are Ivy.",
            emotion_config=PersonaEmotionConfig()
        )
        
        str_repr = str(persona)
        assert "Ivy" in str_repr
        assert "emotions=" in str_repr
        
        repr_repr = repr(persona)
        assert "Persona" in repr_repr
        assert "Ivy" in repr_repr
        assert "You are Ivy" in repr_repr


if __name__ == "__main__":
    pytest.main([__file__, "-v"])