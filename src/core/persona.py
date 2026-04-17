"""
人设数据模型模块
定义人设角色和情绪配置的数据结构
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class PersonaEmotionConfig:
    """人设情绪配置 - 控制情绪表达的行为"""
    default_emotion: str = field(default="neutral")
    allowed_emotions: List[str] = field(default_factory=lambda: ["happy", "sad", "neutral"])
    blocked_emotions: List[str] = field(default_factory=list)
    expression_intensity: float = field(default=0.7)
    material_package: str = field(default="kaomoji_cute")  # 素材包名称，非对象引用
    
    def __post_init__(self):
        """验证配置一致性"""
        if not 0.0 <= self.expression_intensity <= 1.0:
            raise ValueError(f"Expression intensity must be between 0.0 and 1.0, got {self.expression_intensity}")
        
        if self.default_emotion in self.blocked_emotions:
            raise ValueError(f"Default emotion '{self.default_emotion}' cannot be in blocked emotions")
        
        # 确保默认情绪在允许的情绪列表中
        if self.default_emotion not in self.allowed_emotions:
            self.allowed_emotions.append(self.default_emotion)
    
    def is_emotion_allowed(self, emotion: str) -> bool:
        """检查情绪是否被允许
        
        Args:
            emotion: 情绪名称
            
        Returns:
            是否允许该情绪
        """
        if emotion in self.blocked_emotions:
            return False
        if not self.allowed_emotions:  # 如果允许列表为空，则允许所有情绪
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
            allowed_emotions=data.get("allowed_emotions", ["happy", "sad", "neutral"]),
            blocked_emotions=data.get("blocked_emotions", []),
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
            raw_data: 原始YAML数据（便于调试和扩展）
            logger: 可选的日志记录器
        """
        self.name = name
        self.system_prompt = system_prompt
        self.emotion_config = emotion_config
        self.raw_data = raw_data or {}
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
        # 提取基本信息
        name = yaml_data.get("name", "Unnamed")
        
        # 构建系统提示词
        system_prompt = cls._build_system_prompt(yaml_data)
        
        # 创建情绪配置
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
        parts = []
        
        # 基本信息
        name = yaml_data.get("name", "")
        gender = yaml_data.get("gender", "")
        age = yaml_data.get("age", "")
        identity = yaml_data.get("identity", "")
        
        if name:
            parts.append(f"You are {name}.")
        if gender:
            parts.append(f"Gender: {gender}.")
        if age:
            parts.append(f"Age: {age}.")
        if identity:
            parts.append(f"Identity: {identity}.")
        
        # 背景信息
        background = yaml_data.get("background", {})
        if isinstance(background, dict):
            education = background.get("education", "")
            dreams = background.get("dreams", [])
            
            if education:
                parts.append(f"Education: {education}")
            if dreams:
                parts.append(f"Dreams: {', '.join(dreams) if isinstance(dreams, list) else dreams}")
        elif isinstance(background, str):
            parts.append(f"Background: {background}")
        
        # 个性特征
        personality = yaml_data.get("personality", {})
        if isinstance(personality, dict):
            core_traits = personality.get("core_traits", [])
            if core_traits:
                traits_str = ", ".join(core_traits) if isinstance(core_traits, list) else core_traits
                parts.append(f"Personality traits: {traits_str}")
        
        # 如果没有构建出任何内容，使用默认提示词
        if not parts:
            return f"You are {name or 'a character'}."
        
        return " ".join(parts)
    
    @staticmethod
    def _create_emotion_config(yaml_data: Dict[str, Any]) -> PersonaEmotionConfig:
        """从YAML数据创建情绪配置
        
        Args:
            yaml_data: YAML数据
            
        Returns:
            情绪配置对象
        """
        # 从YAML中提取情绪配置
        emotion_data = yaml_data.get("emotion", {})
        
        return PersonaEmotionConfig.from_dict({
            "default_emotion": emotion_data.get("default", "neutral"),
            "allowed_emotions": emotion_data.get("allowed", ["happy", "sad", "neutral"]),
            "blocked_emotions": emotion_data.get("blocked", []),
            "expression_intensity": emotion_data.get("intensity", 0.7),
            "material_package": emotion_data.get("material_package", "kaomoji_cute")
        })
    
    def get_system_context(self) -> str:
        """获取系统上下文（与system_prompt相同，预留格式化接口）
        
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
                setattr(self.emotion_config, key, value)
        
        # 重新验证
        self.emotion_config.__post_init__()
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