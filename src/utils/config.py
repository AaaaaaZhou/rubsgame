"""
全局配置管理模块
支持优先级：命令行参数 > 环境变量 > YAML配置文件
"""
import os
import yaml
from typing import Any, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class AppConfig:
    """应用配置单例类"""
    _instance: Optional['AppConfig'] = None
    
    # LLM 配置
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 1024
    llm_structured_output: bool = True
    
    # 路径配置
    persona_dir: str = "assets/personas/"
    world_dir: str = "assets/world/"
    material_dir: str = "assets/materials/"
    session_dir: str = "data/sessions/"
    log_dir: str = "data/logs/"
    
    # 情绪引擎配置
    emotion_enabled: bool = True
    emotion_default: str = "neutral"
    emotion_render_position: str = "after"
    emotion_material_provider: str = "kaomoji"
    emotion_intensity_low: float = 0.3
    emotion_intensity_medium: float = 0.6
    emotion_intensity_high: float = 0.9
    
    # 记忆引擎配置
    memory_refine_strategy: str = "balanced"
    memory_compression_ratio: float = 0.5
    memory_max_session_memories: int = 10
    memory_auto_refine_on_exit: bool = True
    memory_extractor_type: str = "rule_based"
    
    # 日志配置
    log_level: str = "INFO"
    log_file: str = "data/logs/runtime.log"
    log_max_file_size: int = 10485760
    log_backup_count: int = 5
    log_enable_console: bool = True
    
    # 会话配置
    session_max_history_turns: int = 20
    session_token_limit: int = 4000
    session_auto_save_interval: int = 10
    
    # 开发模式
    dev_mode: bool = False
    
    def __new__(cls, config_path: str = "config/settings.yaml"):
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super(AppConfig, cls).__new__(cls)
            cls._instance._load_config(config_path)
        return cls._instance
    
    def _load_config(self, config_path: str):
        """加载配置（按优先级）"""
        # 1. 从YAML文件加载默认值
        file_config = self._load_yaml_config(config_path)
        
        # 2. 从环境变量覆盖
        env_config = self._load_env_config()
        
        # 3. 合并配置（环境变量优先于YAML文件）
        self._merge_configs(file_config, env_config)
    
    def _load_yaml_config(self, config_path: str) -> Dict[str, Any]:
        """从YAML文件加载配置"""
        if not os.path.exists(config_path):
            print(f"警告：配置文件不存在，使用默认值: {config_path}")
            return {}
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"警告：无法加载配置文件 {config_path}: {e}")
            return {}
    
    def _load_env_config(self) -> Dict[str, Any]:
        """从环境变量加载配置"""
        env_config = {}
        
        # LLM 相关环境变量
        if api_key := os.getenv("LLM_API_KEY"):
            env_config["llm_api_key"] = api_key
        
        if base_url := os.getenv("LLM_BASE_URL"):
            env_config["llm_base_url"] = base_url
        
        # 路径相关环境变量
        if persona_dir := os.getenv("PERSONA_DIR"):
            env_config["persona_dir"] = persona_dir
        
        if world_dir := os.getenv("WORLD_DIR"):
            env_config["world_dir"] = world_dir
        
        # 情绪引擎
        if emotion_enabled := os.getenv("EMOTION_ENABLED"):
            env_config["emotion_enabled"] = emotion_enabled.lower() == "true"
        
        # 记忆引擎
        if refine_strategy := os.getenv("MEMORY_REFINE_STRATEGY"):
            env_config["memory_refine_strategy"] = refine_strategy
        
        # 日志
        if log_level := os.getenv("LOG_LEVEL"):
            env_config["log_level"] = log_level
        
        # 开发模式
        if dev_mode := os.getenv("DEV_MODE"):
            env_config["dev_mode"] = dev_mode.lower() == "true"
        
        return env_config
    
    def _merge_configs(self, file_config: Dict[str, Any], env_config: Dict[str, Any]):
        """合并配置字典到实例属性"""
        # 处理嵌套字典结构
        def flatten_dict(d, parent_key='', sep='_'):
            """将嵌套字典展平为单层字典"""
            items = []
            for k, v in d.items():
                new_key = f"{parent_key}{sep}{k}" if parent_key else k
                if isinstance(v, dict):
                    items.extend(flatten_dict(v, new_key, sep=sep).items())
                else:
                    items.append((new_key, v))
            return dict(items)
        
        # 展平YAML配置
        flat_file_config = flatten_dict(file_config)
        
        # 先应用YAML配置
        for key, value in flat_file_config.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
        # 再应用环境变量配置（覆盖YAML）
        for key, value in env_config.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def get_llm_config(self) -> Dict[str, Any]:
        """获取LLM配置字典"""
        return {
            "api_key": self.llm_api_key,
            "base_url": self.llm_base_url,
            "model": self.llm_model,
            "temperature": self.llm_temperature,
            "max_tokens": self.llm_max_tokens,
            "structured_output": self.llm_structured_output
        }
    
    def get_paths_config(self) -> Dict[str, str]:
        """获取路径配置字典"""
        return {
            "persona_dir": self.persona_dir,
            "world_dir": self.world_dir,
            "material_dir": self.material_dir,
            "session_dir": self.session_dir,
            "log_dir": self.log_dir
        }
    
    def get_emotion_config(self) -> Dict[str, Any]:
        """获取情绪引擎配置字典"""
        return {
            "enabled": self.emotion_enabled,
            "default": self.emotion_default,
            "render_position": self.emotion_render_position,
            "material_provider": self.emotion_material_provider,
            "intensity_thresholds": {
                "low": self.emotion_intensity_low,
                "medium": self.emotion_intensity_medium,
                "high": self.emotion_intensity_high
            }
        }
    
    def get_memory_config(self) -> Dict[str, Any]:
        """获取记忆引擎配置字典"""
        return {
            "refine_strategy": self.memory_refine_strategy,
            "compression_ratio": self.memory_compression_ratio,
            "max_session_memories": self.memory_max_session_memories,
            "auto_refine_on_exit": self.memory_auto_refine_on_exit,
            "extractor_type": self.memory_extractor_type
        }
    
    def get_logging_config(self) -> Dict[str, Any]:
        """获取日志配置字典"""
        return {
            "level": self.log_level,
            "file": self.log_file,
            "max_file_size": self.log_max_file_size,
            "backup_count": self.log_backup_count,
            "enable_console": self.log_enable_console
        }
    
    def get_session_config(self) -> Dict[str, Any]:
        """获取会话配置字典"""
        return {
            "max_history_turns": self.session_max_history_turns,
            "token_limit": self.session_token_limit,
            "auto_save_interval": self.session_auto_save_interval
        }


# 全局配置实例
config = AppConfig()