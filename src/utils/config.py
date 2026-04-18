"""
全局配置管理模块
支持优先级：YAML配置文件 > 环境变量 > 默认值
"""
import os
import yaml
import threading
from typing import Any, Dict, List, Optional

from .logger import get_logger

DEFAULT_CONFIG_PATH = "config/settings.yaml"
DEFAULT_LLM_CONFIG_PATH = "config/llm_config.yaml"

_logger = get_logger("rubsgame.config")


def _parse_float(value: str) -> Optional[float]:
    try:
        return float(value)
    except ValueError:
        return None


def _parse_int(value: str) -> Optional[int]:
    try:
        return int(value)
    except ValueError:
        return None


def _flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '_') -> Dict[str, Any]:
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


class AppConfig:
    """全局配置类（单例模式）

    配置优先级：YAML配置文件 > 环境变量 > 默认值

    注意：单例实例在首次访问时创建，之后的构造调用会返回同一实例，
    传入的参数将被忽略。使用 reset() 方法可重置实例（主要用于测试）。
    """

    _instance: Optional['AppConfig'] = None
    _lock = threading.Lock()

    def __init__(
        self,
        config_path: str = DEFAULT_CONFIG_PATH,
        model_name: Optional[str] = None
    ):
        if AppConfig._instance is not None:
            return

        with AppConfig._lock:
            if AppConfig._instance is not None:
                return
            AppConfig._instance = self

        self._llm_models: Dict[str, Dict[str, Any]] = {}
        self._default_llm_model = "deepseek-reasoner"
        self._current_llm_model = ""

        self.persona_dir = "assets/personas/"
        self.world_dir = "assets/world/"
        self.material_dir = "assets/materials/"
        self.session_dir = "data/sessions/"
        self.log_dir = "data/logs/"

        self.emotion_enabled = True
        self.emotion_default = "neutral"
        self.emotion_render_position = "after"
        self.emotion_material_provider = "kaomoji"
        self.emotion_intensity_low = 0.3
        self.emotion_intensity_medium = 0.6
        self.emotion_intensity_high = 0.9

        self.memory_refine_strategy = "balanced"
        self.memory_compression_ratio = 0.5
        self.memory_max_session_memories = 10
        self.memory_auto_refine_on_exit = True
        self.memory_extractor_type = "rule_based"

        self.log_level = "INFO"
        self.log_file = "data/logs/runtime.log"
        self.log_max_file_size = 10485760
        self.log_backup_count = 5
        self.log_enable_console = True

        self.session_max_history_turns = 20
        self.session_token_limit = 4000
        self.session_auto_save_interval = 10

        self.dev_mode = False

        self._load_config(config_path, model_name)

    def _load_config(self, config_path: str, model_name: Optional[str]):
        yaml_config = self._load_yaml_config(config_path)
        env_config = self._load_env_config()

        flat_yaml = _flatten_dict(yaml_config)
        for key, value in flat_yaml.items():
            if hasattr(self, key):
                setattr(self, key, value)

        for key, value in env_config.items():
            if hasattr(self, key):
                setattr(self, key, value)

        self._load_llm_config(model_name)

    def _load_llm_config(self, model_name: Optional[str]):
        llm_config = self._load_yaml_config(DEFAULT_LLM_CONFIG_PATH)
        self._llm_models = llm_config.get("models", {})
        self._default_llm_model = llm_config.get("default_model", "deepseek-reasoner")

        if model_name and model_name in self._llm_models:
            self._current_llm_model = model_name
        else:
            self._current_llm_model = self._default_llm_model

        _logger.info(f"Loaded {len(self._llm_models)} LLM models, default: {self._default_llm_model}")

        self._apply_llm_env_overrides()

    def _apply_llm_env_overrides(self):
        for model_name, model_config in self._llm_models.items():
            prefix = f"LLM_{model_name.upper().replace('-', '_').replace('.', '_')}"

            if not model_config.get("api_key"):
                if val := os.getenv(f"{prefix}_API_KEY"):
                    model_config["api_key"] = val
                elif val := os.getenv("LLM_API_KEY"):
                    model_config["api_key"] = val

            if not model_config.get("base_url"):
                if val := os.getenv(f"{prefix}_BASE_URL"):
                    model_config["base_url"] = val
                elif val := os.getenv("LLM_BASE_URL"):
                    model_config["base_url"] = val

            if model_config.get("temperature") is None:
                if val := os.getenv(f"{prefix}_TEMPERATURE"):
                    if parsed := _parse_float(val):
                        model_config["temperature"] = parsed

            if model_config.get("max_tokens") is None:
                if val := os.getenv(f"{prefix}_MAX_TOKENS"):
                    if parsed := _parse_int(val):
                        model_config["max_tokens"] = parsed

    def _load_yaml_config(self, config_path: str) -> Dict[str, Any]:
        if not os.path.exists(config_path):
            _logger.warning(f"Config file not found: {config_path}")
            return {}
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                _logger.info(f"Loaded config: {config_path}")
                return config or {}
        except Exception as e:
            _logger.error(f"Failed to load {config_path}: {e}")
            return {}

    def _load_env_config(self) -> Dict[str, Any]:
        env_config = {}
        mappings = {
            "PERSONA_DIR": "persona_dir",
            "WORLD_DIR": "world_dir",
            "MATERIAL_DIR": "material_dir",
            "SESSION_DIR": "session_dir",
            "LOG_DIR": "log_dir",
            "LOG_LEVEL": "log_level",
            "MEMORY_REFINE_STRATEGY": "memory_refine_strategy",
            "EMOTION_ENABLED": "emotion_enabled",
            "DEV_MODE": "dev_mode",
        }
        for env_key, attr in mappings.items():
            if val := os.getenv(env_key):
                if attr in ("emotion_enabled", "dev_mode"):
                    val = val.lower() == "true"
                env_config[attr] = val

        if val := os.getenv("MEMORY_COMPRESSION_RATIO"):
            if parsed := _parse_float(val):
                env_config["memory_compression_ratio"] = parsed

        return env_config

    @property
    def llm_models(self) -> Dict[str, Dict[str, Any]]:
        return self._llm_models

    @property
    def default_llm_model(self) -> str:
        return self._default_llm_model

    @property
    def current_llm_model(self) -> str:
        return self._current_llm_model

    def get_llm_config(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        if model_name is None:
            model_name = self._current_llm_model
        if model_name not in self._llm_models:
            _logger.warning(f"Model '{model_name}' not found, using default '{self._default_llm_model}'")
            model_name = self._default_llm_model
        return self._llm_models.get(model_name, {})

    def set_current_llm_model(self, model_name: str) -> bool:
        if model_name in self._llm_models:
            self._current_llm_model = model_name
            _logger.info(f"LLM model set to: {model_name}")
            return True
        _logger.error(f"Model '{model_name}' not found in available models")
        return False

    def get_available_models(self) -> List[str]:
        return list(self._llm_models.keys())

    def get_paths_config(self) -> Dict[str, str]:
        return {
            "persona_dir": self.persona_dir,
            "world_dir": self.world_dir,
            "material_dir": self.material_dir,
            "session_dir": self.session_dir,
            "log_dir": self.log_dir
        }

    def get_emotion_config(self) -> Dict[str, Any]:
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
        return {
            "refine_strategy": self.memory_refine_strategy,
            "compression_ratio": self.memory_compression_ratio,
            "max_session_memories": self.memory_max_session_memories,
            "auto_refine_on_exit": self.memory_auto_refine_on_exit,
            "extractor_type": self.memory_extractor_type
        }

    def get_logging_config(self) -> Dict[str, Any]:
        return {
            "level": self.log_level,
            "file": self.log_file,
            "max_file_size": self.log_max_file_size,
            "backup_count": self.log_backup_count,
            "enable_console": self.log_enable_console
        }

    def get_session_config(self) -> Dict[str, Any]:
        return {
            "max_history_turns": self.session_max_history_turns,
            "token_limit": self.session_token_limit,
            "auto_save_interval": self.session_auto_save_interval
        }

    @classmethod
    def reset(cls) -> None:
        """重置单例实例（主要用于测试）"""
        with cls._lock:
            cls._instance = None

    @classmethod
    def get_instance(cls, **kwargs) -> 'AppConfig':
        """获取单例实例，未创建则创建之"""
        if cls._instance is None:
            cls(**kwargs)
        return cls._instance


config = AppConfig()
