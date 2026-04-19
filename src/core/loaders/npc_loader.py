"""
NPC 资源加载器
从 assets/npc/{npc_name}/ 目录加载 persona.yaml、relationships.yaml、memories/
"""
import os
import logging
from typing import Dict, List, Optional

from .base import FileReader
from ..persona import Persona
from ..npc import NPCRelationship, NPCMemory, NPCProfile


class NPCLoader:
    """NPC 加载器 - 加载完整 NPC 档案"""

    def __init__(
        self,
        file_reader: FileReader,
        npc_dir: str,
        logger: Optional[logging.Logger] = None
    ):
        self.file_reader = file_reader
        self.npc_dir = npc_dir
        self._logger = logger or logging.getLogger("npc.loader")
        self._loaded_npcs: Dict[str, NPCProfile] = {}

    def load(self, npc_name: str) -> NPCProfile:
        """加载完整 NPC 档案

        Args:
            npc_name: NPC 名称（目录名）

        Returns:
            NPCProfile 对象
        """
        if npc_name in self._loaded_npcs:
            return self._loaded_npcs[npc_name]

        persona = self._load_persona(npc_name)
        relationships = self._load_relationships(npc_name)
        memories = self._load_memories(npc_name)

        profile = NPCProfile(
            persona=persona,
            relationships=relationships,
            private_memories=memories,
        )
        self._loaded_npcs[npc_name] = profile
        self._logger.info(f"NPC '{npc_name}' loaded: {len(relationships)} relations, {len(memories)} memories")
        return profile

    def reload(self, npc_name: str) -> NPCProfile:
        """重新加载 NPC（清除缓存）"""
        if npc_name in self._loaded_npcs:
            del self._loaded_npcs[npc_name]
        return self.load(npc_name)

    def clear_cache(self) -> None:
        self._loaded_npcs.clear()

    def _npc_dir(self, npc_name: str) -> str:
        return os.path.join(self.npc_dir, npc_name)

    def _load_persona(self, npc_name: str) -> Persona:
        """加载 persona.yaml"""
        persona_path = os.path.join(self._npc_dir(npc_name), "persona.yaml")
        if not self.file_reader.file_exists(persona_path):
            raise FileNotFoundError(f"NPC persona not found: {persona_path}")

        yaml_data = self.file_reader.read_yaml(persona_path)
        persona = Persona.create_from_yaml_data(yaml_data)
        self._logger.debug(f"Loaded persona for '{npc_name}'")
        return persona

    def _load_relationships(self, npc_name: str) -> Dict[str, NPCRelationship]:
        """加载 relationships.yaml"""
        rel_path = os.path.join(self._npc_dir(npc_name), "relationships.yaml")
        relationships = {}

        if self.file_reader.file_exists(rel_path):
            yaml_data = self.file_reader.read_yaml(rel_path)
            for obj_id, rel_data in yaml_data.items():
                rel_data["subject_id"] = npc_name
                rel_data["object_id"] = obj_id
                relationships[obj_id] = NPCRelationship.from_dict(rel_data)
            self._logger.debug(f"Loaded {len(relationships)} relationships for '{npc_name}'")

        return relationships

    def _load_memories(self, npc_name: str) -> List[NPCMemory]:
        """扫描 memories/ 目录加载所有 .yaml 文件"""
        mem_dir = os.path.join(self._npc_dir(npc_name), "memories")
        memories = []

        if not self.file_reader.file_exists(mem_dir):
            return memories

        for filename in os.listdir(mem_dir):
            if filename.endswith(".yaml"):
                mem_path = os.path.join(mem_dir, filename)
                try:
                    yaml_data = self.file_reader.read_yaml(mem_path)
                    yaml_data["owner_id"] = npc_name
                    memories.append(NPCMemory.from_dict(yaml_data))
                except Exception as e:
                    self._logger.warning(f"Failed to load memory {filename}: {e}")

        self._logger.debug(f"Loaded {len(memories)} memories for '{npc_name}'")
        return memories

    def get_cached(self, npc_name: str) -> Optional[NPCProfile]:
        return self._loaded_npcs.get(npc_name)
