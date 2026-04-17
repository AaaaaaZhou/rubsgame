"""
数据加载器模块
提供统一的文件加载抽象接口，支持依赖注入和模拟测试
"""

from .base import FileReader, YamlFileReader, BaseDataLoader
from .persona_loader import PersonaLoader
from .world_loader import WorldLoader

__all__ = [
    "FileReader",
    "YamlFileReader", 
    "BaseDataLoader",
    "PersonaLoader",
    "WorldLoader",
]