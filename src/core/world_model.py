"""
世界观数据模型模块
定义世界观地点和全局记忆的数据结构
"""
import logging
from typing import Dict, List, Any, Optional

from .types import MemoryItem


class Location:
    """世界观地点"""

    def __init__(
        self,
        name: str,
        description: str = "",
        npcs: Optional[List[str]] = None,
        properties: Optional[Dict[str, Any]] = None
    ):
        """初始化地点

        Args:
            name: 地点名称
            description: 地点描述
            npcs: NPC列表
            properties: 动态属性字典
        """
        self.name = name
        self.description = description
        self.npcs = npcs if npcs is not None else []
        self.properties = properties if properties is not None else {}

    def add_npc(self, npc_name: str) -> None:
        """添加NPC到地点
        
        Args:
            npc_name: NPC名称
        """
        if npc_name not in self.npcs:
            self.npcs.append(npc_name)
    
    def remove_npc(self, npc_name: str) -> bool:
        """从地点移除NPC
        
        Args:
            npc_name: NPC名称
            
        Returns:
            是否成功移除
        """
        if npc_name in self.npcs:
            self.npcs.remove(npc_name)
            return True
        return False
    
    def set_property(self, key: str, value: Any) -> None:
        """设置地点属性
        
        Args:
            key: 属性键
            value: 属性值
        """
        self.properties[key] = value
    
    def get_property(self, key: str, default: Any = None) -> Any:
        """获取地点属性
        
        Args:
            key: 属性键
            default: 默认值
            
        Returns:
            属性值或默认值
        """
        return self.properties.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "npcs": self.npcs,
            "properties": self.properties,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Location":
        """从字典创建地点"""
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            npcs=data.get("npcs", []),
            properties=data.get("properties", {})
        )
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"Location(name={self.name!r}, npcs={len(self.npcs)})"


class WorldKnowledge:
    """世界观知识库 - 管理地点和全局记忆"""
    
    def __init__(
        self,
        world_name: str,
        logger: Optional[logging.Logger] = None
    ):
        """初始化世界观
        
        Args:
            world_name: 世界观名称
            logger: 可选的日志记录器
        """
        self.world_name = world_name
        self.locations: List[Location] = []
        self.global_memories: List[MemoryItem] = []

        self._logger = logger or logging.getLogger(f"world.{world_name}")
        self._logger.info(f"World '{world_name}' initialized")
    
    def add_location(self, location: Location) -> None:
        """添加地点到世界观
        
        Args:
            location: 地点对象
        """
        # 检查名称是否已存在
        for loc in self.locations:
            if loc.name == location.name:
                self._logger.warning(f"Location '{location.name}' already exists, updating")
                loc.description = location.description
                loc.npcs = location.npcs
                loc.properties = location.properties
                return
        
        self.locations.append(location)
        self._logger.debug(f"Added location: {location.name}")
    
    def get_location(self, name: str) -> Optional[Location]:
        """获取指定名称的地点
        
        Args:
            name: 地点名称
            
        Returns:
            地点对象或None
        """
        for location in self.locations:
            if location.name == name:
                return location
        return None
    
    def add_global_memory(self, content: str, priority: int = 5, tags: Optional[List[str]] = None) -> MemoryItem:
        """添加全局记忆

        Args:
            content: 记忆内容
            priority: 优先级 (0-10)
            tags: 标签列表

        Returns:
            创建的MemoryItem对象
        """
        memory = MemoryItem(
            content=content,
            memory_type="world_global",
            priority=priority,
            tags=tags or []
        )
        
        # 简单的去重检查（基于内容）
        for existing in self.global_memories:
            if existing.content == content:
                self._logger.debug(f"Memory already exists: {content[:50]}...")
                return existing
        
        self.global_memories.append(memory)
        self._logger.debug(f"Added global memory: {content[:50]}...")
        return memory
    
    def add_existing_memory(self, memory: MemoryItem) -> None:
        """添加已存在的记忆项（通常来自会话）
        
        Args:
            memory: 记忆项对象
        """
        if memory.memory_type != "world_global":
            self._logger.warning(f"Memory type '{memory.memory_type}' may not be appropriate for world storage")
        
        # 简单的去重检查
        for existing in self.global_memories:
            if existing.content == memory.content:
                self._logger.debug(f"Memory already exists: {memory.content[:50]}...")
                return
        
        self.global_memories.append(memory)
        self._logger.debug(f"Added existing memory: {memory.content[:50]}...")
    
    def get_system_context(self) -> str:
        """生成系统上下文描述
        
        Returns:
            世界观描述文本
        """
        if not self.locations:
            return f"World: {self.world_name}"
        
        parts = [f"World: {self.world_name}", "Locations:"]
        
        for location in self.locations:
            parts.append(f"- {location.name}: {location.description}")
            if location.npcs:
                npcs_str = ", ".join(location.npcs)
                parts.append(f"  NPCs: {npcs_str}")
        
        # 添加重要的全局记忆
        important_memories = [m for m in self.global_memories if m.priority >= 7]
        if important_memories:
            parts.append("Important World Knowledge:")
            for memory in important_memories[:5]:  # 最多显示5个重要记忆
                parts.append(f"- {memory.content}")
        
        return "\n".join(parts)
    
    def query_locations(self, keyword: str) -> List[Location]:
        """查询包含关键词的地点
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            匹配的地点列表
        """
        keyword_lower = keyword.lower()
        results = []
        
        for location in self.locations:
            if (keyword_lower in location.name.lower() or 
                keyword_lower in location.description.lower()):
                results.append(location)
        
        return results
    
    def query_memories(self, keyword: str) -> List[MemoryItem]:
        """查询包含关键词的全局记忆
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            匹配的记忆项列表
        """
        keyword_lower = keyword.lower()
        results = []
        
        for memory in self.global_memories:
            if keyword_lower in memory.content.lower():
                results.append(memory)
        
        return results
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典
        
        Returns:
            包含世界观数据的字典
        """
        return {
            "world_name": self.world_name,
            "locations": [loc.to_dict() for loc in self.locations],
            "global_memories": [mem.to_dict() for mem in self.global_memories],
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldKnowledge":
        """从字典恢复世界观

        Args:
            data: 世界观数据字典

        Returns:
            恢复的WorldKnowledge对象
        """
        world = cls(world_name=data["world_name"])

        # 恢复地点
        for loc_data in data.get("locations", []):
            world.locations.append(Location.from_dict(loc_data))

        # 恢复全局记忆
        for mem_data in data.get("global_memories", []):
            world.global_memories.append(MemoryItem.from_dict(mem_data))
        
        world._logger.info(f"World '{world.world_name}' restored from dict")
        return world
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取世界观统计信息
        
        Returns:
            统计信息字典
        """
        return {
            "world_name": self.world_name,
            "location_count": len(self.locations),
            "memory_count": len(self.global_memories),
            "total_npcs": sum(len(loc.npcs) for loc in self.locations),
            "avg_memory_priority": sum(m.priority for m in self.global_memories) / len(self.global_memories) if self.global_memories else 0,
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        stats = self.get_statistics()
        return f"WorldKnowledge(name={self.world_name!r}, locations={stats['location_count']}, memories={stats['memory_count']})"
    
    def __repr__(self) -> str:
        """详细表示"""
        return f"WorldKnowledge(world_name={self.world_name!r})"