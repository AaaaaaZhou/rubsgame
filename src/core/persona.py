"""
人设数据模型模块
定义人设角色和情绪配置的数据结构
"""
import logging
from typing import Dict, List, Any, Optional


class PersonaEmotionConfig:
    """人设情绪配置 - 控制情绪表达的行为"""

    def __init__(
        self,
        default_emotion: str = "neutral",
        allowed_emotions: Optional[List[str]] = None,
        blocked_emotions: Optional[List[str]] = None,
        expression_intensity: float = 0.7,
        material_package: str = "kaomoji_cute"
    ):
        """初始化情绪配置

        Args:
            default_emotion: 默认情绪
            allowed_emotions: 允许的情绪列表，None时默认为["happy", "sad", "neutral"]
            blocked_emotions: 禁止的情绪列表
            expression_intensity: 表达强度 (0.0-1.0)
            material_package: 素材包名称
        """
        if not 0.0 <= expression_intensity <= 1.0:
            raise ValueError(f"Expression intensity must be between 0.0 and 1.0, got {expression_intensity}")

        if blocked_emotions is None:
            blocked_emotions = []
        if allowed_emotions is None:
            allowed_emotions = ["happy", "sad", "neutral"]

        # 确保默认情绪在允许的情绪列表中（在构造时一次性完成，不留副作用）
        if default_emotion not in allowed_emotions:
            allowed_emotions = [default_emotion] + allowed_emotions

        if default_emotion in blocked_emotions:
            raise ValueError(f"Default emotion '{default_emotion}' cannot be in blocked emotions")

        self.default_emotion = default_emotion
        self.allowed_emotions = allowed_emotions
        self.blocked_emotions = blocked_emotions
        self.expression_intensity = expression_intensity
        self.material_package = material_package

    def is_emotion_allowed(self, emotion: str) -> bool:
        """检查情绪是否被允许

        Args:
            emotion: 情绪名称

        Returns:
            是否允许该情绪
        """
        if emotion in self.blocked_emotions:
            return False
        if not self.allowed_emotions:
            return True
        return emotion in self.allowed_emotions

    def filter_emotions(self, emotions: List[str]) -> List[str]:
        """过滤情绪列表，移除被禁止的情绪

        Args:
            emotions: 原始情绪列表

        Returns:
            过滤后的情绪列表
        """
        return [e for e in emotions if self.is_emotion_allowed(e)]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "default_emotion": self.default_emotion,
            "allowed_emotions": self.allowed_emotions,
            "blocked_emotions": self.blocked_emotions,
            "expression_intensity": self.expression_intensity,
            "material_package": self.material_package,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PersonaEmotionConfig":
        """从字典创建配置"""
        return cls(
            default_emotion=data.get("default_emotion", "neutral"),
            allowed_emotions=data.get("allowed_emotions"),
            blocked_emotions=data.get("blocked_emotions"),
            expression_intensity=data.get("expression_intensity", 0.7),
            material_package=data.get("material_package", "kaomoji_cute")
        )


class Persona:
    """人设角色 - 包含角色定义和情绪配置"""

    def __init__(
        self,
        name: str,
        system_prompt: str,
        emotion_config: PersonaEmotionConfig,
        raw_data: Optional[Dict[str, Any]] = None,
        logger: Optional[logging.Logger] = None
    ):
        """初始化人设

        Args:
            name: 角色名称
            system_prompt: 系统提示词
            emotion_config: 情绪配置
            raw_data: 原始YAML数据
            logger: 可选的日志记录器
        """
        self.name = name
        self.system_prompt = system_prompt
        self.emotion_config = emotion_config
        self.raw_data = raw_data if raw_data is not None else {}
        self._logger = logger or logging.getLogger(f"persona.{name}")

        self._logger.info(f"Persona '{name}' initialized")

    @classmethod
    def create_from_yaml_data(cls, yaml_data: Dict[str, Any]) -> "Persona":
        """从YAML数据创建人设（工厂方法）

        Args:
            yaml_data: 解析后的YAML数据

        Returns:
            创建的人设对象
        """
        name = yaml_data.get("name", "Unnamed")
        system_prompt = cls._build_system_prompt(yaml_data)
        emotion_config = cls._create_emotion_config(yaml_data)

        return cls(
            name=name,
            system_prompt=system_prompt,
            emotion_config=emotion_config,
            raw_data=yaml_data
        )

    @staticmethod
    def _build_system_prompt(yaml_data: Dict[str, Any]) -> str:
        """从YAML数据构建系统提示词

        Args:
            yaml_data: YAML数据

        Returns:
            系统提示词字符串
        """
        sections = []

        # Basic identity
        name = yaml_data.get("name", "")
        identity = yaml_data.get("identity", "")
        sections.append(f"You are {name}. {identity}")

        # Background section
        background = yaml_data.get("background", {})
        if isinstance(background, dict):
            bg_parts = []
            if education := background.get("education", ""):
                bg_parts.append(f"Education: {education}")
            if dreams := background.get("dreams", []):
                dream_str = ", ".join(dreams) if isinstance(dreams, list) else str(dreams)
                bg_parts.append(f"Dreams: {dream_str}")
            if limitations := background.get("limitations", []):
                limit_str = ", ".join(limitations) if isinstance(limitations, list) else str(limitations)
                bg_parts.append(f"Limitations: {limit_str}")
            if bg_parts:
                sections.append(f"\n## Background\n" + "\n".join(bg_parts))

        # Personality section
        personality = yaml_data.get("personality", {})
        if isinstance(personality, dict):
            perf_parts = []
            if core_traits := personality.get("core_traits", []):
                traits_str = ", ".join(core_traits) if isinstance(core_traits, list) else core_traits
                perf_parts.append(f"Core traits: {traits_str}")
            prefs = personality.get("preferences", {})
            if isinstance(prefs, dict):
                if likes := prefs.get("likes", []):
                    perf_parts.append(f"Likes: {', '.join(likes)}")
                if dislikes := prefs.get("dislikes", []):
                    perf_parts.append(f"Dislikes: {', '.join(dislikes)}")
            if perf_parts:
                sections.append(f"\n## Personality\n" + "\n".join(perf_parts))

        # Speech style section
        speech_style = yaml_data.get("speech_style", {})
        if isinstance(speech_style, dict):
            ss_parts = []
            if tone := speech_style.get("tone", ""):
                ss_parts.append(f"Tone: {tone}")
            if vocab := speech_style.get("vocabulary", ""):
                ss_parts.append(f"Vocabulary: {vocab}")
            if features := speech_style.get("features", []):
                ss_parts.append(f"Features: {', '.join(features)}")
            if ss_parts:
                sections.append(f"\n## Speech Style\n" + "\n".join(ss_parts))

        # Behaviors section
        behaviors = yaml_data.get("behaviors", {})
        if isinstance(behaviors, dict):
            beh_parts = []
            if conflict := behaviors.get("conflict_response", {}):
                desc = conflict.get("description", "") if isinstance(conflict, dict) else conflict
                if desc:
                    beh_parts.append(f"Conflict response: {desc}")
            if social := behaviors.get("social_interaction", {}):
                desc = social.get("description", "") if isinstance(social, dict) else social
                if desc:
                    beh_parts.append(f"Social interaction: {desc}")
            if beh_parts:
                sections.append(f"\n## Behaviors\n" + "\n".join(beh_parts))

        # Mood system section
        mood_system = yaml_data.get("mood_system", {})
        if isinstance(mood_system, dict):
            mood_parts = []
            if baseline := mood_system.get("baseline"):
                mood_parts.append(f"Baseline mood: {baseline}")
            factors = mood_system.get("factors", {})
            if isinstance(factors, dict):
                if pos := factors.get("positive", []):
                    mood_parts.append(f"Positive factors: {', '.join(pos)}")
                if neg := factors.get("negative", []):
                    mood_parts.append(f"Negative factors: {', '.join(neg)}")
            if mood_parts:
                sections.append(f"\n## Mood System\n" + "\n".join(mood_parts))

        # Topics of interest
        topics = yaml_data.get("topics_of_interest", [])
        if topics:
            topics_str = ", ".join(topics) if isinstance(topics, list) else str(topics)
            sections.append(f"\n## Topics of Interest\n{topics_str}")

        return "\n".join(sections) if sections else f"You are {name or 'a character'}."

    @staticmethod
    def _create_emotion_config(yaml_data: Dict[str, Any]) -> PersonaEmotionConfig:
        """从YAML数据创建情绪配置

        Args:
            yaml_data: YAML数据

        Returns:
            情绪配置对象
        """
        emotion_data = yaml_data.get("emotion", {})

        return PersonaEmotionConfig.from_dict({
            "default_emotion": emotion_data.get("default", "neutral"),
            "allowed_emotions": emotion_data.get("allowed", ["happy", "sad", "neutral"]),
            "blocked_emotions": emotion_data.get("blocked", []),
            "expression_intensity": emotion_data.get("intensity", 0.7),
            "material_package": emotion_data.get("material_package", "kaomoji_cute")
        })

    def get_system_context(self) -> str:
        """获取系统上下文

        Returns:
            系统上下文字符串
        """
        return self.system_prompt

    def update_emotion_config(self, **kwargs) -> None:
        """更新情绪配置

        Args:
            **kwargs: 情绪配置字段
        """
        for key, value in kwargs.items():
            if hasattr(self.emotion_config, key):
                if key == "expression_intensity" and not 0.0 <= value <= 1.0:
                    raise ValueError(f"Expression intensity must be between 0.0 and 1.0, got {value}")
                if key == "default_emotion" and value in self.emotion_config.blocked_emotions:
                    raise ValueError(f"Default emotion '{value}' cannot be in blocked emotions")
                setattr(self.emotion_config, key, value)

        # 确保新的默认情绪在允许列表中
        if self.emotion_config.default_emotion not in self.emotion_config.allowed_emotions:
            self.emotion_config.allowed_emotions.insert(0, self.emotion_config.default_emotion)

        self._logger.debug(f"Emotion config updated: {kwargs}")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化）

        Returns:
            包含人设数据的字典
        """
        return {
            "name": self.name,
            "system_prompt": self.system_prompt,
            "emotion_config": self.emotion_config.to_dict(),
            "raw_data": self.raw_data
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Persona":
        """从字典恢复人设

        Args:
            data: 人设数据字典

        Returns:
            恢复的人设对象
        """
        emotion_config = PersonaEmotionConfig.from_dict(data["emotion_config"])

        return cls(
            name=data["name"],
            system_prompt=data["system_prompt"],
            emotion_config=emotion_config,
            raw_data=data.get("raw_data", {})
        )

    def __str__(self) -> str:
        """字符串表示"""
        return f"Persona(name={self.name!r}, emotions={len(self.emotion_config.allowed_emotions)})"

    def __repr__(self) -> str:
        """详细表示"""
        return f"Persona(name={self.name!r}, system_prompt={self.system_prompt[:50]}...)"
