"""
PlotLoader tests
"""
import sys
import os
import tempfile
import shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import pytest
from src.core.plot.plot_loader import PlotLoader
from src.core.plot.types import NodeType, NarrativeType


class MockFileReader:
    """Mock file reader for testing"""
    def __init__(self):
        self.files = {}

    def add_file(self, path, data):
        self.files[path] = data

    def read_yaml(self, file_path):
        if file_path not in self.files:
            raise FileNotFoundError(f"File not found: {file_path}")
        import yaml
        return yaml.safe_load(self.files[file_path])

    def file_exists(self, file_path):
        return file_path in self.files


class TestPlotLoader:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.reader = MockFileReader()
        self.loader = PlotLoader(self.reader, self.temp_dir)

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_chapter_yaml(self, chapter_id, content_yaml):
        chapter_dir = os.path.join(self.temp_dir, chapter_id)
        os.makedirs(chapter_dir, exist_ok=True)
        file_path = os.path.join(chapter_dir, "chapter.yaml")
        self.reader.add_file(file_path, content_yaml)
        return file_path

    def test_load_simple_chapter(self):
        yaml_content = """
chapter:
  id: "test_ch1"
  name: "Test Chapter"

nodes:
  - id: "n1"
    node_type: "NARRATION_ONLY"
    narration_type: "SCENE_ENTER"
    content: "You arrive at the old street"
    next: "n2"

  - id: "n2"
    node_type: "DIALOGUE"
    npc_name: "alice"
    content: "Welcome!"
"""
        self._write_chapter_yaml("test_ch1", yaml_content)
        chapter = self.loader.load("test_ch1")

        assert chapter.id == "test_ch1"
        assert chapter.name == "Test Chapter"
        assert len(chapter.nodes) == 2

        assert chapter.nodes[0].id == "n1"
        assert chapter.nodes[0].node_type == NodeType.NARRATION_ONLY
        assert chapter.nodes[0].narration_type == NarrativeType.SCENE_ENTER

        assert chapter.nodes[1].id == "n2"
        assert chapter.nodes[1].node_type == NodeType.DIALOGUE
        assert chapter.nodes[1].npc_name == "alice"

    def test_load_chapter_with_branches(self):
        yaml_content = """
chapter:
  id: "test_ch2"
  name: "Branch Test"

nodes:
  - id: "n1"
    node_type: "BRANCH"
    narration_type: "FREE_EXPLORE"
    branches:
      - id: "b1"
        label: "Choice A"
        next_node: "n2a"
      - id: "b2"
        label: "Choice B"
        next_node: "n2b"
      - id: "b3"
        label: "(Free Input)"
        next_node: "n2c"
"""
        self._write_chapter_yaml("test_ch2", yaml_content)
        chapter = self.loader.load("test_ch2")

        assert len(chapter.nodes) == 1
        node = chapter.nodes[0]
        assert node.node_type == NodeType.BRANCH
        assert len(node.branches) == 3
        assert node.branches[0].label == "Choice A"
        assert node.branches[0].next_node == "n2a"
        assert node.branches[2].label == "(Free Input)"

    def test_load_chapter_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            self.loader.load("nonexistent_chapter")

    def test_caching(self):
        yaml_content = """
chapter:
  id: "test_ch3"
  name: "Cache Test"

nodes:
  - id: "n1"
    node_type: "DIALOGUE"
    content: "Test"
"""
        self._write_chapter_yaml("test_ch3", yaml_content)

        ch1 = self.loader.load("test_ch3")
        ch2 = self.loader.load("test_ch3")
        assert ch1 is ch2

    def test_reload_clears_cache(self):
        yaml_content = """
chapter:
  id: "test_ch4"
  name: "Original Name"

nodes:
  - id: "n1"
    node_type: "DIALOGUE"
    content: "Test"
"""
        self._write_chapter_yaml("test_ch4", yaml_content)

        ch1 = self.loader.load("test_ch4")
        assert ch1.name == "Original Name"

        yaml_content2 = """
chapter:
  id: "test_ch4"
  name: "New Name"

nodes:
  - id: "n1"
    node_type: "DIALOGUE"
    content: "Test"
"""
        self._write_chapter_yaml("test_ch4", yaml_content2)

        ch2 = self.loader.reload("test_ch4")
        assert ch2.name == "New Name"

    def test_clear_cache(self):
        yaml_content = """
chapter:
  id: "test_ch5"
  name: "Test"

nodes:
  - id: "n1"
    node_type: "DIALOGUE"
    content: "Test"
"""
        self._write_chapter_yaml("test_ch5", yaml_content)

        self.loader.load("test_ch5")
        assert len(self.loader.get_cached_chapters()) == 1

        self.loader.clear_cache()
        assert len(self.loader.get_cached_chapters()) == 0