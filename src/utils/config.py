"""
全局配置管理模块
支持优先级：命令行参数 > 环境变量 > YAML配置文件
"""
import os
import yaml
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Union, List, TypeVar, cast
from dataclasses import dataclass, field

# 导入项目日志系统
from .logger import get_logger

# 类型别名
T = TypeVar('T')

# 常量定义
DEFAULT_CONFIG_PATH = "config/settings.yaml"
DEFAULT_LLM_CONFIG_PATH = "config/llm_config.yaml"
ENV_PREFIX = "LLM_"

# 模块级Logger
_logger = get_logger("rubsgame.config")


@dataclass
class AppConfig:
    """应用配置单例类"""
    _instance: Optional['AppConfig'] = None
    _lock: threading.Lock = threading.Lock()
    
    # LLM 模型配置（从 llm_config.yaml 加载）
    llm_models: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    default_llm_model: str = "gpt-4o-mini"
    current_llm_model: str = ""
    
    # LLM 配置（向后兼容字段，优先使用 llm_models 中的配置）
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
    
    def __new__(cls, config_path: str = DEFAULT_CONFIG_PATH, model_name: Optional[str] = None):
        """线程安全的单例模式实现"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(AppConfig, cls).__new__(cls)
                cls._instance._load_config(config_path, model_name)
        return cls._instance
    
    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH, model_name: Optional[str] = None):
        """初始化配置实例
        
        注意：此方法被dataclass的__init__覆盖，需要调用super().__init__()
        实际配置加载已在__new__中完成，此处仅处理参数覆盖
        """
        # 必须调用super().__init__()以确保dataclass字段正确初始化
        super().__init__()
        
        # 如果提供了模型名称且当前模型未设置，更新当前模型
        if model_name:
            self.set_current_llm_model(model_name)
    
    def _load_config(self, config_path: str, model_name: Optional[str] = None):
        """加载配置（按优先级）"""
        # 1. 从YAML文件加载默认值
        file_config = self._load_yaml_config(config_path)
        
        # 2. 从环境变量覆盖
        env_config = self._load_env_config()
        
        # 3. 合并配置（环境变量优先于YAML文件）
        self._merge_configs(file_config, env_config)
        
        # 4. 加载LLM模型配置
        self._load_llm_config(model_name)
    
    def _load_llm_config(self, model_name: Optional[str] = None):
        """加载LLM模型配置"""
        # 1. 从YAML文件加载LLM配置
        llm_config = self._load_yaml_config(DEFAULT_LLM_CONFIG_PATH)
        
        # 2. 存储模型配置
        self.llm_models = llm_config.get("models", {})
        self.default_llm_model = llm_config.get("default_model", "gpt-4o-mini")
        
        # 3. 设置当前模型
        if model_name and model_name in self.llm_models:
            self.current_llm_model = model_name
        else:
            self.current_llm_model = self.default_llm_model
        
        # 4. 记录加载的模型信息
        _logger.info(f"加载 {len(self.llm_models)} 个LLM模型配置，默认模型: {self.default_llm_model}")
        
        # 5. 应用环境变量覆盖
        self._apply_llm_env_overrides()
        
        # 6. 设置向后兼容字段（使用当前模型的配置）
        if self.current_llm_model in self.llm_models:
            model_config = self.llm_models[self.current_llm_model]
            self.llm_api_key = model_config.get("api_key", "")
            self.llm_base_url = model_config.get("base_url", "https://api.openai.com/v1")
            self.llm_model = model_config.get("model", self.current_llm_model)
            self.llm_temperature = model_config.get("temperature", 0.7)
            self.llm_max_tokens = model_config.get("max_tokens", 1024)
            self.llm_structured_output = model_config.get("structured_output", True)
    
    def _apply_llm_env_overrides(self):
        """应用LLM环境变量覆盖"""
        for model_name, model_config in self.llm_models.items():
            # 通用环境变量（适用于所有模型）
            if api_key := os.getenv("LLM_API_KEY"):
                model_config["api_key"] = api_key
                _logger.debug(f"应用通用环境变量 LLM_API_KEY 到模型 {model_name}")
            
            if base_url := os.getenv("LLM_BASE_URL"):
                model_config["base_url"] = base_url
                _logger.debug(f"应用通用环境变量 LLM_BASE_URL 到模型 {model_name}")
            
            # 模型特定环境变量
            model_prefix = f"LLM_{model_name.upper().replace('-', '_')}"
            
            if model_specific_api_key := os.getenv(f"{model_prefix}_API_KEY"):
                model_config["api_key"] = model_specific_api_key
                _logger.debug(f"应用模型特定环境变量 {model_prefix}_API_KEY 到模型 {model_name}")
            
            if model_specific_base_url := os.getenv(f"{model_prefix}_BASE_URL"):
                model_config["base_url"] = model_specific_base_url
                _logger.debug(f"应用模型特定环境变量 {model_prefix}_BASE_URL 到模型 {model_name}")
            
            if model_specific_temp := os.getenv(f"{model_prefix}_TEMPERATURE"):
                try:
                    model_config["temperature"] = float(model_specific_temp)
                    _logger.debug(f"应用模型特定环境变量 {model_prefix}_TEMPERATURE 到模型 {model_name}")
                except ValueError as e:
                    _logger.warning(f"环境变量 {model_prefix}_TEMPERATURE 值 '{model_specific_temp}' 无法转换为浮点数: {e}")
            
            if model_specific_tokens := os.getenv(f"{model_prefix}_MAX_TOKENS"):
                try:
                    model_config["max_tokens"] = int(model_specific_tokens)
                    _logger.debug(f"应用模型特定环境变量 {model_prefix}_MAX_TOKENS 到模型 {model_name}")
                except ValueError as e:
                    _logger.warning(f"环境变量 {model_prefix}_MAX_TOKENS 值 '{model_specific_tokens}' 无法转换为整数: {e}")
    
    def _load_yaml_config(self, config_path: str) -> Dict[str, Any]:
        """从YAML文件加载配置"""
        if not os.path.exists(config_path):
            _logger.warning(f"配置文件不存在，使用默认值: {config_path}")
            return {}
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                _logger.info(f"成功加载配置文件: {config_path}")
                return config or {}
        except Exception as e:
            _logger.error(f"无法加载配置文件 {config_path}: {e}")
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
        
        if material_dir := os.getenv("MATERIAL_DIR"):
            env_config["material_dir"] = material_dir
        
        if session_dir := os.getenv("SESSION_DIR"):
            env_config["session_dir"] = session_dir
        
        if log_dir := os.getenv("LOG_DIR"):
            env_config["log_dir"] = log_dir
        
        # 情绪引擎
        if emotion_enabled := os.getenv("EMOTION_ENABLED"):
            env_config["emotion_enabled"] = emotion_enabled.lower() == "true"
        
        # 记忆引擎
        if refine_strategy := os.getenv("MEMORY_REFINE_STRATEGY"):
            env_config["memory_refine_strategy"] = refine_strategy
        
        if compression_ratio := os.getenv("MEMORY_COMPRESSION_RATIO"):
            try:
                env_config["memory_compression_ratio"] = float(compression_ratio)
            except ValueError:
                _logger.warning(f"环境变量 MEMORY_COMPRESSION_RATIO 值 '{compression_ratio}' 无法转换为浮点数")
        
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
                _logger.debug(f"应用YAML配置 {key} = {value}")
        
        # 再应用环境变量配置（覆盖YAML）
        for key, value in env_config.items():
            if hasattr(self, key):
                setattr(self, key, value)
                _logger.debug(f"应用环境变量配置 {key} = {value}")
    
    # ========== 公共API方法 ==========
    
    def get_llm_config(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """获取LLM配置字典
        
        Args:
            model_name: 模型名称，如果为None则使用当前模型
            
        Returns:
            LLM配置字典，包含api_key、base_url等字段
        """
        # 确定要使用的模型
        if model_name is None:
            model_name = self.current_llm_model
        
        # 如果模型不存在，使用默认模型
        if model_name not in self.llm_models:
            _logger.warning(f"模型 '{model_name}' 不存在，使用默认模型 '{self.default_llm_model}'")
            model_name = self.default_llm_model
        
        # 获取模型配置
        model_config = self.llm_models.get(model_name, {})
        
        # 返回配置字典
        return {
            "api_key": model_config.get("api_key", ""),
            "base_url": model_config.get("base_url", "https://api.openai.com/v1"),
            "model": model_config.get("model", model_name),
            "temperature": model_config.get("temperature", 0.7),
            "max_tokens": model_config.get("max_tokens", 1024),
            "structured_output": model_config.get("structured_output", True),
            "model_name": model_name  # 添加模型名称到返回字典
        }
    
    def set_current_llm_model(self, model_name: str) -> bool:
        """设置当前LLM模型
        
        Args:
            model_name: 模型名称
            
        Returns:
            是否成功设置
        """
        if model_name in self.llm_models:
            self.current_llm_model = model_name
            
            # 更新向后兼容字段
            model_config = self.llm_models[model_name]
            self.llm_api_key = model_config.get("api_key", "")
            self.llm_base_url = model_config.get("base_url", "https://api.openai.com/v1")
            self.llm_model = model_config.get("model", model_name)
            self.llm_temperature = model_config.get("temperature", 0.7)
            self.llm_max_tokens = model_config.get("max_tokens", 1024)
            self.llm_structured_output = model_config.get("structured_output", True)
            
            _logger.info(f"当前LLM模型已设置为: {model_name}")
            return True
        else:
            _logger.error(f"设置当前LLM模型失败: 模型 '{model_name}' 不存在")
            return False
    
    def get_available_models(self) -> List[str]:
        """获取所有可用模型名称列表"""
        return list(self.llm_models.keys())
    
    def validate_config(self) -> bool:
        """验证配置有效性"""
        errors = []
        
        # 验证LLM模型配置
        if not self.llm_models:
            errors.append("未加载任何LLM模型配置")
        
        if self.current_llm_model not in self.llm_models:
            errors.append(f"当前模型 '{self.current_llm_model}' 不在可用模型列表中")
        
        # 验证路径配置
        for path_name, path_value in [
            ("persona_dir", self.persona_dir),
            ("world_dir", self.world_dir),
            ("material_dir", self.material_dir),
            ("session_dir", self.session_dir),
            ("log_dir", self.log_dir),
        ]:
            if not path_value:
                errors.append(f"路径配置 '{path_name}' 为空")
        
        if errors:
            _logger.error(f"配置验证失败: {errors}")
            return False
        
        _logger.info("配置验证通过")
        return True
    
    # ========== 便捷属性（property） ==========
    
    @property
    def llm_config(self) -> Dict[str, Any]:
        """获取当前LLM配置的便捷属性"""
        return self.get_llm_config()
    
    @property
    def current_llm_model_config(self) -> Dict[str, Any]:
        """获取当前LLM模型配置的便捷属性"""
        return self.get_llm_config(self.current_llm_model)
    
    # ========== 各模块配置获取方法 ==========
    
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