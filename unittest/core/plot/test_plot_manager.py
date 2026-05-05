"""
StoryPlotManager tests
"""
import sys
import os
import tempfile
import shutil
import yaml
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import pytest
from src.core.plot.types import NodeType, NarrativeType, PlotContext, InteractionTrigger
from src.core.plot.types import Chapter, PlotNode, Branch


class MockAssetManager:
    def __init__(self):
        self._world = None
        self._file_reader = MockFileReader()  # Needed by StoryPlotManager.__init__

    def set_world(self, world):
        self._world = world

    def get_current_world(self):
        return self._world


class MockWorld:
    def __init__(self, locations):
        self.locations = locations

    def get_location(self, name):
        for loc in self.locations:
            if loc.name == name:
                return loc
        return None


class MockLocation:
    def __init__(self, name):
        self.name = name


class MockFileReader:
    def __init__(self):
        self.files = {}

    def add_file(self, path, data):
        # Store as already-parsed dict
        self.files[path] = data

    def read_yaml(self, path):
        if path not in self.files:
            raise FileNotFoundError(f"File not found: {path}")
        data = self.files[path]
        # If it's already a dict, return as-is
        if isinstance(data, dict):
            return data
        # Otherwise parse as YAML string
        import yaml
        return yaml.safe_load(data)

    def file_exists(self, path):
        return path in self.files


class TestStoryPlotManager:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mock_reader = MockFileReader()
        self.mock_asset = MockAssetManager()

        # Patch PlotLoader.__init__ to accept our mock reader
        from src.core.plot import plot_loader as pl_module
        self._orig_plot_init = pl_module.PlotLoader.__init__

        def patched_init(loader_self, reader, base_dir, logger=None):
            # Call original but then override file_reader
            pl_module.BaseDataLoader.__init__(loader_self, reader, base_dir, logger)
            loader_self.file_reader = reader
            loader_self._loaded_chapters = {}
            loader_self._logger = logger or __import__('logging').getLogger("test")

        pl_module.PlotLoader.__init__ = patched_init

    def teardown_method(self):
        from src.core.plot import plot_loader as pl_module
        pl_module.PlotLoader.__init__ = self._orig_plot_init
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_chapter(self, chapter_id, nodes, name="Test Chapter"):
        chapter_dir = os.path.join(self.temp_dir, chapter_id)
        os.makedirs(chapter_dir, exist_ok=True)
        file_path = os.path.join(chapter_dir, "chapter.yaml")
        data = {
            "chapter": {"id": chapter_id, "name": name},
            "nodes": nodes
        }
        self.mock_reader.add_file(file_path, data)

    def _create_loader(self):
        from src.core.plot.plot_loader import PlotLoader
        return PlotLoader(self.mock_reader, self.temp_dir)

    def test_load_chapter(self):
        self._write_chapter("ch1", [
            {"id": "n1", "node_type": "NARRATION_ONLY", "narration_type": "SCENE_ENTER",
             "content": "You arrive", "next": "n2"},
            {"id": "n2", "node_type": "DIALOGUE", "npc_name": "alice", "content": "Hi!"}
        ])
        from src.core.plot.plot_manager import StoryPlotManager
        manager = StoryPlotManager(self.mock_asset, self.temp_dir)
        manager._loader = self._create_loader()

        chapter = manager.load_chapter("ch1")

        assert chapter.id == "ch1"
        assert len(chapter.nodes) == 2
        assert manager.get_current_state().chapter_id == "ch1"
        assert manager.get_current_state().node_id == "n1"

    def test_advance_to(self):
        self._write_chapter("ch2", [
            {"id": "n1", "node_type": "NARRATION_ONLY", "content": "Start"},
            {"id": "n2", "node_type": "DIALOGUE", "content": "Middle"},
            {"id": "n3", "node_type": "NARRATION_ONLY", "content": "End"}
        ])
        from src.core.plot.plot_manager import StoryPlotManager
        manager = StoryPlotManager(self.mock_asset, self.temp_dir)
        manager._loader = self._create_loader()
        manager.load_chapter("ch2")

        node = manager.advance_to("n2")
        assert node.id == "n2"
        assert manager.get_current_state().node_id == "n2"

    def test_make_choice(self):
        self._write_chapter("ch3", [
            {"id": "n1", "node_type": "BRANCH", "narration_type": "FREE_EXPLORE",
             "branches": [
                 {"id": "b1", "label": "Go left", "next_node": "n2a"},
                 {"id": "b2", "label": "Go right", "next_node": "n2b"}
             ]},
            {"id": "n2a", "node_type": "DIALOGUE", "content": "Left path"},
            {"id": "n2b", "node_type": "DIALOGUE", "content": "Right path"}
        ])
        from src.core.plot.plot_manager import StoryPlotManager
        manager = StoryPlotManager(self.mock_asset, self.temp_dir)
        manager._loader = self._create_loader()
        manager.load_chapter("ch3")

        assert manager.get_current_state().is_branch_point is True
        choices = manager.get_available_choices()
        assert len(choices) == 2

        node = manager.make_choice("b2")
        assert node.id == "n2b"
        assert manager.get_current_state().is_branch_point is False

    def test_is_exploring(self):
        self._write_chapter("ch4", [
            {"id": "n1", "node_type": "NARRATION_ONLY", "content": "Start"}
        ])
        from src.core.plot.plot_manager import StoryPlotManager
        manager = StoryPlotManager(self.mock_asset, self.temp_dir)
        manager._loader = self._create_loader()
        manager.load_chapter("ch4")

        assert manager.is_exploring() is False
        manager.get_current_state().is_exploring = True
        assert manager.is_exploring() is True

    def test_get_available_locations(self):
        temp_asset = MockAssetManager()
        temp_asset.set_world(MockWorld([
            MockLocation("Old Street"),
            MockLocation("Cafe"),
            MockLocation("River")
        ]))

        from src.core.plot.plot_manager import StoryPlotManager
        manager = StoryPlotManager(temp_asset, self.temp_dir)
        locs = manager.get_available_locations()
        assert "Old Street" in locs
        assert "Cafe" in locs
        assert "River" in locs

    def test_move_to_location(self):
        temp_asset = MockAssetManager()
        temp_asset.set_world(MockWorld([MockLocation("Old Street")]))

        from src.core.plot.plot_manager import StoryPlotManager
        manager = StoryPlotManager(temp_asset, self.temp_dir)
        result = manager.move_to_location("Old Street")
        assert result is True
        assert manager.is_exploring() is True

        result = manager.move_to_location("Nonexistent")
        assert result is False

    def test_check_triggers(self):
        self._write_chapter("ch5", [
            {"id": "n1", "node_type": "DIALOGUE", "content": "Test",
             "triggers": [
                 {"type": "STORY_PROGRESS", "event": "test_event"}
             ]}
        ])
        from src.core.plot.plot_manager import StoryPlotManager
        temp_asset = MockAssetManager()
        manager = StoryPlotManager(temp_asset, self.temp_dir)
        manager._loader = self._create_loader()
        manager.load_chapter("ch5")

        context = PlotContext(current_chapter="ch5", current_node="n1")
        triggers = manager.check_triggers(context)
        assert len(triggers) == 1
        assert triggers[0].event == "test_event"

    def test_advance_to_nonexistent_node_raises(self):
        self._write_chapter("ch6", [
            {"id": "n1", "node_type": "DIALOGUE", "content": "Start"}
        ])
        from src.core.plot.plot_manager import StoryPlotManager
        manager = StoryPlotManager(self.mock_asset, self.temp_dir)
        manager._loader = self._create_loader()
        manager.load_chapter("ch6")

        with pytest.raises(ValueError, match="Node not found"):
            manager.advance_to("nonexistent_node")

    def test_make_choice_invalid_branch_raises(self):
        self._write_chapter("ch7", [
            {"id": "n1", "node_type": "BRANCH", "narration_type": "FREE_EXPLORE",
             "branches": [
                 {"id": "b1", "label": "Choice A", "next_node": "n2a"}
             ]},
            {"id": "n2a", "node_type": "DIALOGUE", "content": "A"}
        ])
        from src.core.plot.plot_manager import StoryPlotManager
        manager = StoryPlotManager(self.mock_asset, self.temp_dir)
        manager._loader = self._create_loader()
        manager.load_chapter("ch7")

        with pytest.raises(ValueError, match="Branch not found"):
            manager.make_choice("invalid_branch_id")

    def test_get_available_locations_no_world(self):
        from src.core.plot.plot_manager import StoryPlotManager
        temp_asset = MockAssetManager()
        temp_asset._world = None
        manager = StoryPlotManager(temp_asset, self.temp_dir)
        locs = manager.get_available_locations()
        assert locs == []

    def test_get_current_node(self):
        self._write_chapter("ch8", [
            {"id": "n1", "node_type": "DIALOGUE", "content": "First"},
            {"id": "n2", "node_type": "DIALOGUE", "content": "Second"}
        ])
        from src.core.plot.plot_manager import StoryPlotManager
        manager = StoryPlotManager(self.mock_asset, self.temp_dir)
        manager._loader = self._create_loader()
        manager.load_chapter("ch8")

        node = manager.get_current_node()
        assert node is not None
        assert node.id == "n1"

        manager.advance_to("n2")
        node = manager.get_current_node()
        assert node.id == "n2"

    def test_get_current_node_no_chapter(self):
        from src.core.plot.plot_manager import StoryPlotManager
        manager = StoryPlotManager(self.mock_asset, self.temp_dir)
        assert manager.get_current_node() is None

    def test_get_current_chapter_no_chapter_loaded(self):
        from src.core.plot.plot_manager import StoryPlotManager
        manager = StoryPlotManager(self.mock_asset, self.temp_dir)
        assert manager.get_current_chapter() is None

    def test_load_chapter_sets_branch_point_flag(self):
        self._write_chapter("ch9", [
            {"id": "n1", "node_type": "BRANCH", "narration_type": "FREE_EXPLORE",
             "branches": [
                 {"id": "b1", "label": "A", "next_node": "n2"}
             ]}
        ])
        from src.core.plot.plot_manager import StoryPlotManager
        manager = StoryPlotManager(self.mock_asset, self.temp_dir)
        manager._loader = self._create_loader()
        manager.load_chapter("ch9")

        state = manager.get_current_state()
        assert state.is_branch_point is True
        assert state.chapter_id == "ch9"

    def test_load_chapter_non_branch_sets_not_branch_point(self):
        self._write_chapter("ch10", [
            {"id": "n1", "node_type": "DIALOGUE", "content": "Just talking"}
        ])
        from src.core.plot.plot_manager import StoryPlotManager
        manager = StoryPlotManager(self.mock_asset, self.temp_dir)
        manager._loader = self._create_loader()
        manager.load_chapter("ch10")

        state = manager.get_current_state()
        assert state.is_branch_point is False

    def test_move_to_location_no_world(self):
        from src.core.plot.plot_manager import StoryPlotManager
        temp_asset = MockAssetManager()
        temp_asset._world = None
        manager = StoryPlotManager(temp_asset, self.temp_dir)
        result = manager.move_to_location("Anywhere")
        assert result is False

    def test_move_to_location_valid_sets_exploring(self):
        temp_asset = MockAssetManager()
        temp_asset.set_world(MockWorld([MockLocation("Cafe")]))
        from src.core.plot.plot_manager import StoryPlotManager
        manager = StoryPlotManager(temp_asset, self.temp_dir)
        result = manager.move_to_location("Cafe")
        assert result is True
        assert manager.is_exploring() is True