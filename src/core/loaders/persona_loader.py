"""
人设数据加载器
从YAML文件加载人设角色配置
"""
import os
import logging
from typing import Dict, Any, Optional

from .base import BaseDataLoader, FileReader
from ..persona import Persona


class PersonaLoader(BaseDataLoader):
    """人设加载器 - 负责加载和解析人设YAML文件"""
    
    def __init__(
        self,
        file_reader: FileReader,
        base_dir: str,
        logger: Optional[logging.Logger] = None
    ):
        """初始化人设加载器
        
        Args:
            file_reader: 文件读取器
            base_dir: 人设文件基础目录
            logger: 可选的日志记录器
        """
        super().__init__(file_reader, base_dir, logger)
        self._loaded_personas: Dict[str, Persona] = {}  # 简单缓存
        self._log_info(f"PersonaLoader initialized with base_dir: {base_dir}")
    
    def load(self, persona_name: str) -> Persona:
        """加载指定名称的人设（支持新旧路径兼容）

        路径查找顺序：
        1. 新路径: {base_dir}/{persona_name}/persona.yaml
        2. 回退: {base_dir}/{persona_name}.yaml

        Args:
            persona_name: 人设名称（对应目录名或文件名）

        Returns:
            加载的Persona对象

        Raises:
            FileNotFoundError: 人设文件不存在
            ValueError: 人设数据格式错误
        """
        # 检查缓存
        if persona_name in self._loaded_personas:
            self._log_debug(f"Returning cached persona: {persona_name}")
            return self._loaded_personas[persona_name]

        file_path = self._resolve_persona_path(persona_name)
        self._log_debug(f"Loading persona from: {file_path}")

        try:
            # 读取YAML数据
            yaml_data = self.file_reader.read_yaml(file_path)
            self._log_debug(f"Successfully read YAML for persona: {persona_name}")

            # 验证基本结构
            if not isinstance(yaml_data, dict):
                raise ValueError(f"Persona YAML must be a dictionary, got {type(yaml_data)}")

            # 创建人设对象
            persona = Persona.create_from_yaml_data(yaml_data)
            self._log_info(f"Persona '{persona_name}' loaded successfully")

            # 缓存结果
            self._loaded_personas[persona_name] = persona
            return persona

        except Exception as e:
            self._log_error(f"Failed to load persona '{persona_name}': {e}", exc_info=True)
            raise

    def _resolve_persona_path(self, persona_name: str) -> str:
        """解析 persona 文件路径，按优先级尝试：
        1. {base_dir}/{name}/persona.yaml (新路径)
        2. {base_dir}/{name}.yaml (旧路径)

        Returns:
            实际存在的文件路径

        Raises:
            FileNotFoundError: 所有路径均不存在
        """
        # 新路径: 子目录下的 persona.yaml
        new_path = os.path.join(self.base_dir, persona_name, "persona.yaml")
        if self.file_reader.file_exists(new_path):
            return new_path

        # 旧路径: 直接的 .yaml 文件
        old_path = os.path.join(self.base_dir, f"{persona_name}.yaml")
        if self.file_reader.file_exists(old_path):
            return old_path

        raise FileNotFoundError(f"Persona file not found (tried: {new_path}, {old_path})")
    
    def load_all(self) -> Dict[str, Persona]:
        """加载所有人设文件（支持新旧路径混合扫描）

        扫描顺序：
        1. 子目录形式: {base_dir}/{subdir}/persona.yaml
        2. 旧文件形式: {base_dir}/{name}.yaml

        Returns:
            人设名称到Persona对象的映射字典
        """
        if not os.path.exists(self.base_dir):
            self._log_warning(f"Persona directory does not exist: {self.base_dir}")
            return {}

        personas = {}
        seen = set()

        # 1. 扫描子目录（新路径）
        for entry in os.listdir(self.base_dir):
            subdir = os.path.join(self.base_dir, entry)
            if os.path.isdir(subdir):
                persona_file = os.path.join(subdir, "persona.yaml")
                if self.file_reader.file_exists(persona_file):
                    try:
                        persona = self.load(entry)
                        personas[entry] = persona
                        seen.add(entry)
                    except Exception as e:
                        self._log_error(f"Failed to load persona from {persona_file}: {e}")

        # 2. 扫描顶层 .yaml 文件（旧路径，排除已加载的子目录名）
        for filename in os.listdir(self.base_dir):
            if filename.endswith(".yaml"):
                persona_name = filename[:-5]  # 移除.yaml扩展名
                if persona_name in seen:
                    continue
                try:
                    persona = self.load(persona_name)
                    personas[persona_name] = persona
                except Exception as e:
                    self._log_error(f"Failed to load persona from {filename}: {e}")

        self._log_info(f"Loaded {len(personas)} personas from {self.base_dir}")
        return personas
    
    def reload(self, persona_name: str) -> Persona:
        """重新加载指定人设（清除缓存）
        
        Args:
            persona_name: 人设名称
            
        Returns:
            重新加载的Persona对象
        """
        # 清除缓存
        if persona_name in self._loaded_personas:
            del self._loaded_personas[persona_name]
            self._log_debug(f"Cleared cache for persona: {persona_name}")
        
        return self.load(persona_name)
    
    def clear_cache(self) -> None:
        """清除所有缓存的人设"""
        count = len(self._loaded_personas)
        self._loaded_personas.clear()
        self._log_info(f"Cleared cache for {count} personas")
    
    def get_cached_personas(self) -> Dict[str, Persona]:
        """获取当前缓存的所有人设
        
        Returns:
            缓存的人设字典
        """
        return self._loaded_personas.copy()
    
    def _log_debug(self, message: str) -> None:
        """记录调试日志"""
        self._logger.debug(f"[PersonaLoader] {message}")
    
    def _log_info(self, message: str) -> None:
        """记录信息日志"""
        self._logger.info(f"[PersonaLoader] {message}")
    
    def _log_warning(self, message: str) -> None:
        """记录警告日志"""
        self._logger.warning(f"[PersonaLoader] {message}")
    
    def _log_error(self, message: str, exc_info: bool = False) -> None:
        """记录错误日志"""
        self._logger.error(f"[PersonaLoader] {message}", exc_info=exc_info)