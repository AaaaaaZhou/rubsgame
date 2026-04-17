"""
世界观数据加载器
从YAML文件加载世界观配置
"""
import os
import logging
from typing import Dict, Any, Optional, List

from .base import BaseDataLoader, FileReader
from ..world_model import WorldKnowledge, Location
from ..session import MemoryItem


class WorldLoader(BaseDataLoader):
    """世界观加载器 - 负责加载和解析世界观YAML文件"""
    
    def __init__(
        self,
        file_reader: FileReader,
        base_dir: str,
        logger: Optional[logging.Logger] = None
    ):
        """初始化世界观加载器
        
        Args:
            file_reader: 文件读取器
            base_dir: 世界观文件基础目录
            logger: 可选的日志记录器
        """
        super().__init__(file_reader, base_dir, logger)
        self._loaded_worlds: Dict[str, WorldKnowledge] = {}  # 简单缓存
        self._log_info(f"WorldLoader initialized with base_dir: {base_dir}")
    
    def load(self, world_name: str) -> WorldKnowledge:
        """加载指定名称的世界观
        
        Args:
            world_name: 世界观名称（对应YAML文件名，不含扩展名）
            
        Returns:
            加载的WorldKnowledge对象
            
        Raises:
            FileNotFoundError: 世界观文件不存在
            ValueError: 世界观数据格式错误
        """
        # 检查缓存
        if world_name in self._loaded_worlds:
            self._log_debug(f"Returning cached world: {world_name}")
            return self._loaded_worlds[world_name]
        
        # 构建文件路径
        file_path = self._get_file_path(world_name, ".yaml")
        self._log_debug(f"Loading world from: {file_path}")
        
        # 检查文件是否存在
        if not self.file_reader.file_exists(file_path):
            # 尝试.json扩展名作为备用
            json_path = self._get_file_path(world_name, ".json")
            if self.file_reader.file_exists(json_path):
                file_path = json_path
                self._log_debug(f"Using JSON file: {json_path}")
            else:
                raise FileNotFoundError(f"World file not found: {file_path} or {json_path}")
        
        try:
            # 读取数据 - 使用文件读取器（支持YAML和JSON）
            data = self.file_reader.read_yaml(file_path)
            
            self._log_debug(f"Successfully read data for world: {world_name}")
            
            # 验证基本结构
            if not isinstance(data, dict):
                raise ValueError(f"World data must be a dictionary, got {type(data)}")
            
            # 创建世界观对象
            world = self._create_world_from_data(world_name, data)
            self._log_info(f"World '{world_name}' loaded successfully")
            
            # 缓存结果
            self._loaded_worlds[world_name] = world
            return world
            
        except Exception as e:
            self._log_error(f"Failed to load world '{world_name}': {e}", exc_info=True)
            raise
    
    def _create_world_from_data(self, world_name: str, data: Dict[str, Any]) -> WorldKnowledge:
        """从数据字典创建世界观对象
        
        Args:
            world_name: 世界观名称
            data: 世界观数据字典
            
        Returns:
            创建的WorldKnowledge对象
        """
        world = WorldKnowledge(world_name=world_name)
        
        # 解析地点
        locations_data = data.get("locations", [])
        if isinstance(locations_data, list):
            for loc_data in locations_data:
                if isinstance(loc_data, dict):
                    location = Location(
                        name=loc_data.get("name", "Unnamed"),
                        description=loc_data.get("description", ""),
                        npcs=loc_data.get("npcs", []),
                        properties=loc_data.get("properties", {})
                    )
                    world.add_location(location)
        
        # 解析全局记忆
        memories_data = data.get("global_memories", [])
        if isinstance(memories_data, list):
            for mem_data in memories_data:
                if isinstance(mem_data, dict):
                    memory = MemoryItem(
                        content=mem_data.get("content", ""),
                        memory_type="world_global",
                        priority=mem_data.get("priority", 5),
                        tags=mem_data.get("tags", [])
                    )
                    world.add_existing_memory(memory)
                elif isinstance(mem_data, str):
                    # 简单字符串作为记忆内容
                    world.add_global_memory(mem_data)
        
        # 解析初始NPC（向后兼容）
        npcs_data = data.get("npcs", [])
        if isinstance(npcs_data, list):
            default_location = world.get_location("Town Square") or world.get_location("Central")
            if not default_location and world.locations:
                default_location = world.locations[0]
            
            if default_location:
                for npc_data in npcs_data:
                    if isinstance(npc_data, dict):
                        npc_name = npc_data.get("name", "Unnamed NPC")
                        default_location.add_npc(npc_name)
                    elif isinstance(npc_data, str):
                        default_location.add_npc(npc_data)
        
        return world
    
    def load_all(self) -> Dict[str, WorldKnowledge]:
        """加载所有世界观文件
        
        Returns:
            世界观名称到WorldKnowledge对象的映射字典
        """
        if not os.path.exists(self.base_dir):
            self._log_warning(f"World directory does not exist: {self.base_dir}")
            return {}
        
        worlds = {}
        for filename in os.listdir(self.base_dir):
            if filename.endswith((".yaml", ".json")):
                world_name = os.path.splitext(filename)[0]
                try:
                    world = self.load(world_name)
                    worlds[world_name] = world
                except Exception as e:
                    self._log_error(f"Failed to load world from {filename}: {e}")
        
        self._log_info(f"Loaded {len(worlds)} worlds from {self.base_dir}")
        return worlds
    
    def reload(self, world_name: str) -> WorldKnowledge:
        """重新加载指定世界观（清除缓存）
        
        Args:
            world_name: 世界观名称
            
        Returns:
            重新加载的WorldKnowledge对象
        """
        # 清除缓存
        if world_name in self._loaded_worlds:
            del self._loaded_worlds[world_name]
            self._log_debug(f"Cleared cache for world: {world_name}")
        
        return self.load(world_name)
    
    def clear_cache(self) -> None:
        """清除所有缓存的世界观"""
        count = len(self._loaded_worlds)
        self._loaded_worlds.clear()
        self._log_info(f"Cleared cache for {count} worlds")
    
    def get_cached_worlds(self) -> Dict[str, WorldKnowledge]:
        """获取当前缓存的所有世界观
        
        Returns:
            缓存的世界观字典
        """
        return self._loaded_worlds.copy()
    
    def create_default_world(self) -> WorldKnowledge:
        """创建默认世界观（当没有找到文件时使用）
        
        Returns:
            默认的WorldKnowledge对象
        """
        world = WorldKnowledge(world_name="Default World")
        
        # 添加一些默认地点
        town_square = Location(
            name="Town Square",
            description="The central gathering place of the town, with a fountain and market stalls."
        )
        world.add_location(town_square)
        
        tavern = Location(
            name="Rusty Tankard Tavern",
            description="A cozy tavern where adventurers gather to share stories and drinks."
        )
        world.add_location(tavern)
        
        self._log_info("Created default world with basic locations")
        return world
    
    def _log_debug(self, message: str) -> None:
        """记录调试日志"""
        self._logger.debug(f"[WorldLoader] {message}")
    
    def _log_info(self, message: str) -> None:
        """记录信息日志"""
        self._logger.info(f"[WorldLoader] {message}")
    
    def _log_warning(self, message: str) -> None:
        """记录警告日志"""
        self._logger.warning(f"[WorldLoader] {message}")
    
    def _log_error(self, message: str, exc_info: bool = False) -> None:
        """记录错误日志"""
        self._logger.error(f"[WorldLoader] {message}", exc_info=exc_info)