"""
剧情章节 YAML 加载器
从 assets/plot/{chapter_id}/chapter.yaml 加载章节配置
"""
import os
import logging
from typing import Any, Dict, List, Optional

from .types import (
    NodeType, TriggerType, NarrativeType, Condition, Branch, Trigger,
    PlotNode, Chapter, InteractionTrigger, NPCInteraction
)
from ..loaders.base import BaseDataLoader, FileReader


class PlotLoader(BaseDataLoader):
    """章节加载器 - 负责加载和解析章节 YAML 文件"""

    def __init__(
        self,
        file_reader: FileReader,
        base_dir: str,
        logger: Optional[logging.Logger] = None
    ):
        """初始化章节加载器

        Args:
            file_reader: 文件读取器
            base_dir: 章节文件基础目录 (assets/plot/)
            logger: 可选的日志记录器
        """
        super().__init__(file_reader, base_dir, logger)
        self._loaded_chapters: Dict[str, Chapter] = {}
        self._log_info(f"PlotLoader initialized with base_dir: {base_dir}")

    def load(self, chapter_id: str) -> Chapter:
        """加载指定章节

        Args:
            chapter_id: 章节 ID

        Returns:
            加载的 Chapter 对象

        Raises:
            FileNotFoundError: 章节文件不存在
            ValueError: 数据格式错误
        """
        if chapter_id in self._loaded_chapters:
            self._log_debug(f"Returning cached chapter: {chapter_id}")
            return self._loaded_chapters[chapter_id]

        chapter_dir = os.path.join(self.base_dir, chapter_id)
        file_path = os.path.join(chapter_dir, "chapter.yaml")

        if not self.file_reader.file_exists(file_path):
            raise FileNotFoundError(f"Chapter file not found: {file_path}")

        try:
            data = self.file_reader.read_yaml(file_path)
            chapter = self._parse_chapter(chapter_id, data)
            self._loaded_chapters[chapter_id] = chapter
            self._log_info(f"Chapter '{chapter_id}' loaded successfully")
            return chapter
        except Exception as e:
            self._log_error(f"Failed to load chapter '{chapter_id}': {e}", exc_info=True)
            raise

    def _parse_chapter(self, chapter_id: str, data: Dict[str, Any]) -> Chapter:
        """解析章节数据"""
        chapter_data = data.get("chapter", {})
        nodes_data = data.get("nodes", [])

        chapter = Chapter(
            id=chapter_id,
            name=chapter_data.get("name", chapter_id)
        )

        for node_data in nodes_data:
            node = self._parse_node(node_data)
            if node:
                chapter.nodes.append(node)

        return chapter

    def _parse_node(self, data: Dict[str, Any]) -> Optional[PlotNode]:
        """解析节点数据"""
        node_type_str = data.get("node_type", "dialogue")
        try:
            node_type = NodeType(node_type_str.lower())
        except ValueError:
            node_type = NodeType.DIALOGUE

        narration_type_str = data.get("narration_type", "free_explore")
        try:
            narration_type = NarrativeType(narration_type_str.lower())
        except ValueError:
            narration_type = NarrativeType.FREE_EXPLORE

        branches = None
        if "branches" in data and isinstance(data["branches"], list):
            branches = [self._parse_branch(b) for b in data["branches"]]

        triggers = []
        if "triggers" in data and isinstance(data["triggers"], list):
            triggers = [self._parse_trigger(t) for t in data["triggers"]]

        return PlotNode(
            id=data["id"],
            node_type=node_type,
            npc_name=data.get("npc_name"),
            content=data.get("content", ""),
            next=data.get("next"),
            branches=branches,
            triggers=triggers,
            narration_type=narration_type
        )

    def _parse_branch(self, data: Dict[str, Any]) -> Branch:
        """解析分支数据"""
        condition = None
        if "condition" in data and isinstance(data["condition"], dict):
            condition = self._parse_condition(data["condition"])

        return Branch(
            id=data["id"],
            label=data["label"],
            condition=condition,
            next_node=data.get("next_node", "")
        )

    def _parse_condition(self, data: Dict[str, Any]) -> Condition:
        """解析条件数据"""
        if data is None:
            return Condition()
        return Condition(
            relationship_min=data.get("relationship_min"),
            relationship_max=data.get("relationship_max"),
            has_item=data.get("has_item"),
            flag=data.get("flag")
        )

    def _parse_trigger(self, data: Dict[str, Any]) -> Trigger:
        """解析触发器数据"""
        trigger_type_str = data.get("type", "story_progress")
        try:
            trigger_type = TriggerType(trigger_type_str)
        except ValueError:
            trigger_type = TriggerType.STORY_PROGRESS

        condition = None
        if "condition" in data and isinstance(data["condition"], dict):
            condition = self._parse_condition(data["condition"])

        return Trigger(
            type=trigger_type,
            condition=condition,
            event=data.get("event", "")
        )

    def reload(self, chapter_id: str) -> Chapter:
        """重新加载章节（清除缓存）"""
        if chapter_id in self._loaded_chapters:
            del self._loaded_chapters[chapter_id]
            self._log_debug(f"Cleared cache for chapter: {chapter_id}")
        return self.load(chapter_id)

    def clear_cache(self) -> None:
        """清除所有缓存的章节"""
        count = len(self._loaded_chapters)
        self._loaded_chapters.clear()
        self._log_info(f"Cleared cache for {count} chapters")

    def get_cached_chapters(self) -> Dict[str, Chapter]:
        """获取当前缓存的所有章节"""
        return self._loaded_chapters.copy()

    def _log_debug(self, message: str) -> None:
        if self._logger:
            self._logger.debug(f"[PlotLoader] {message}")

    def _log_info(self, message: str) -> None:
        if self._logger:
            self._logger.info(f"[PlotLoader] {message}")

    def _log_error(self, message: str, exc_info: bool = False) -> None:
        if self._logger:
            self._logger.error(f"[PlotLoader] {message}", exc_info=exc_info)