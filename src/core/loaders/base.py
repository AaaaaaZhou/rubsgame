"""
数据加载器抽象基类
提供文件读取和数据加载的统一接口，支持依赖注入和测试模拟
"""
import os
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class FileReader(ABC):
    """文件读取抽象接口 - 便于模拟文件系统依赖"""
    
    @abstractmethod
    def read_yaml(self, file_path: str) -> Dict[str, Any]:
        """读取YAML文件并返回字典数据
        
        Args:
            file_path: YAML文件路径
            
        Returns:
            解析后的字典数据
            
        Raises:
            FileNotFoundError: 文件不存在
            yaml.YAMLError: YAML解析错误
        """
        pass
    
    @abstractmethod
    def file_exists(self, file_path: str) -> bool:
        """检查文件是否存在
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件是否存在
        """
        pass


class YamlFileReader(FileReader):
    """YAML文件读取器 - 真实文件系统实现"""
    
    def __init__(self, encoding: str = "utf-8"):
        self.encoding = encoding
    
    def read_yaml(self, file_path: str) -> Dict[str, Any]:
        """读取YAML文件"""
        import yaml
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(file_path, "r", encoding=self.encoding) as f:
            return yaml.safe_load(f) or {}
    
    def file_exists(self, file_path: str) -> bool:
        """检查文件是否存在"""
        return os.path.exists(file_path)


class BaseDataLoader(ABC):
    """数据加载器基类 - 统一依赖注入接口"""
    
    def __init__(
        self,
        file_reader: FileReader,
        base_dir: str,
        logger: Optional[logging.Logger] = None
    ):
        """初始化数据加载器
        
        Args:
            file_reader: 文件读取器实例
            base_dir: 基础目录路径
            logger: 可选的日志记录器
        """
        self.file_reader = file_reader
        self.base_dir = base_dir
        self._logger = logger or logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def load(self, identifier: str) -> Any:
        """加载指定标识符的数据
        
        Args:
            identifier: 数据标识符（如文件名）
            
        Returns:
            加载的数据对象
            
        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 数据格式错误
        """
        pass
    
    def _get_file_path(self, filename: str, extension: str = ".yaml") -> str:
        """构建完整的文件路径
        
        Args:
            filename: 文件名（不含扩展名）
            extension: 文件扩展名
            
        Returns:
            完整的文件路径
        """
        return os.path.join(self.base_dir, f"{filename}{extension}")
    
    def _log_debug(self, message: str) -> None:
        """记录调试日志"""
        if self._logger:
            self._logger.debug(message)
    
    def _log_info(self, message: str) -> None:
        """记录信息日志"""
        if self._logger:
            self._logger.info(message)
    
    def _log_error(self, message: str, exc_info: bool = False) -> None:
        """记录错误日志"""
        if self._logger:
            self._logger.error(message, exc_info=exc_info)