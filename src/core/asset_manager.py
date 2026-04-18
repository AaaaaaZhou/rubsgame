"""
资源管理器模块
统一管理 Persona 和 World，支持热加载
预留 RAG 扩展接口：query_world() 可替换为 RAG 实现
"""
import logging
from typing import Dict, List, Optional

from .persona import Persona
from .world_model import WorldKnowledge, Location
from .types import MemoryItem
from .loaders.base import YamlFileReader
from .loaders.persona_loader import PersonaLoader
from .loaders.world_loader import WorldLoader
from ..utils.config import AppConfig
from ..utils.logger import get_logger

_logger = get_logger("rubsgame.asset")


class AssetManager:
    """资源管理器 - 单例"""

    _instance: Optional["AssetManager"] = None

    def __init__(self, config: Optional[AppConfig] = None):
        if AssetManager._instance is not None:
            return
        AssetManager._instance = self

        self._config = config or AppConfig.get_instance()
        self._persona_loader = PersonaLoader(
            YamlFileReader(),
            self._config.persona_dir
        )
        self._world_loader = WorldLoader(
            YamlFileReader(),
            self._config.world_dir
        )
        self._current_persona: Optional[Persona] = None
        self._current_world: Optional[WorldKnowledge] = None
        _logger.info("AssetManager initialized")

    @classmethod
    def get_instance(cls) -> "AssetManager":
        if cls._instance is None:
            cls()
        return cls._instance

    # ==================== Persona ====================

    def load_persona(self, persona_name: str) -> Persona:
        """加载人设"""
        persona = self._persona_loader.load(persona_name)
        self._current_persona = persona
        _logger.info(f"Loaded persona: {persona_name}")
        return persona

    def get_current_persona(self) -> Optional[Persona]:
        return self._current_persona

    def hot_reload_persona(self, persona_name: str) -> Persona:
        """热加载人设（清除缓存后重新加载）"""
        self._persona_loader.reload(persona_name)
        return self.load_persona(persona_name)

    # ==================== World ====================

    def load_world(self, world_name: str) -> WorldKnowledge:
        """加载世界观"""
        world = self._world_loader.load(world_name)
        self._current_world = world
        _logger.info(f"Loaded world: {world_name}")
        return world

    def get_current_world(self) -> Optional[WorldKnowledge]:
        return self._current_world

    def update_global_memory(self, memory: MemoryItem) -> None:
        """添加全局记忆到当前 World"""
        if self._current_world is None:
            _logger.warning("No world loaded, cannot add global memory")
            return
        self._current_world.add_existing_memory(memory)

    # ==================== RAG-Extensible Query Interface ====================
    # 后续可替换为 RAG 实现，如：query_world_rag(keyword) -> List[str]
    def query_world(self, keyword: str) -> Dict[str, List[str]]:
        """查询世界观中包含关键词的信息

        扩展提示：后续可替换为 RAG 实现，
        返回结构保持一致：{"locations": [...], "memories": [...]}

        Args:
            keyword: 搜索关键词

        Returns:
            匹配结果字典，包含 locations 和 memories
        """
        if self._current_world is None:
            return {"locations": [], "memories": []}

        locations = self._current_world.query_locations(keyword)
        memories = self._current_world.query_memories(keyword)

        return {
            "locations": [loc.name for loc in locations],
            "memories": [m.content for m in memories]
        }

    def get_world_context(self) -> str:
        """获取世界观的系统上下文描述"""
        if self._current_world is None:
            return ""
        return self._current_world.get_system_context()

    def get_persona_system_prompt(self) -> str:
        """获取当前人设的系统提示词"""
        if self._current_persona is None:
            return ""
        return self._current_persona.get_system_context()

    def get_persona_emotion_config(self) -> Optional[Persona]:
        """获取当前人设（包含情绪配置）"""
        return self._current_persona
