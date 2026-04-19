"""
数据加载器测试
"""
import sys
import os
import tempfile
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import pytest
from unittest.mock import patch
from src.core.loaders import FileReader, YamlFileReader, BaseDataLoader, PersonaLoader, WorldLoader
from src.core.persona import Persona
from src.core.world_model import WorldKnowledge


class MockFileReader(FileReader):
    """模拟文件读取器 - 用于测试"""
    
    def __init__(self, files: dict):
        """
        Args:
            files: 文件名到内容的映射字典
        """
        # 规范化路径以确保跨平台一致性
        self.files = {}
        self.directories = set()
        
        for path, content in files.items():
            norm_path = os.path.normpath(path)
            self.files[norm_path] = content
            
            # 提取目录路径
            dir_path = os.path.dirname(norm_path)
            while dir_path and dir_path != os.path.dirname(dir_path):
                self.directories.add(dir_path)
                dir_path = os.path.dirname(dir_path)
    
    def _normalize_path(self, file_path: str) -> str:
        """规范化文件路径"""
        return os.path.normpath(file_path)
    
    def read_yaml(self, file_path: str) -> dict:
        norm_path = self._normalize_path(file_path)
        if norm_path not in self.files:
            raise FileNotFoundError(f"File not found: {file_path}")
        return self.files[norm_path]
    
    def file_exists(self, file_path: str) -> bool:
        norm_path = self._normalize_path(file_path)
        # 检查是否是文件或目录
        return norm_path in self.files or norm_path in self.directories


class TestFileReader:
    """测试文件读取器基类"""
    
    def test_mock_file_reader(self):
        """测试模拟文件读取器"""
        mock_data = {
            "/test/file.yaml": {"key": "value"},
            "/test/another.yaml": {"list": [1, 2, 3]}
        }
        
        reader = MockFileReader(mock_data)
        
        assert reader.file_exists("/test/file.yaml") is True
        assert reader.file_exists("/test/nonexistent.yaml") is False
        
        data = reader.read_yaml("/test/file.yaml")
        assert data["key"] == "value"
        
        with pytest.raises(FileNotFoundError):
            reader.read_yaml("/test/nonexistent.yaml")


class TestYamlFileReader:
    """测试YAML文件读取器"""
    
    def test_read_yaml_from_real_file(self):
        """测试从真实文件读取YAML"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
name: Test
value: 42
list:
  - item1
  - item2
""")
            temp_path = f.name
        
        try:
            reader = YamlFileReader()
            data = reader.read_yaml(temp_path)
            
            assert data["name"] == "Test"
            assert data["value"] == 42
            assert data["list"] == ["item1", "item2"]
        finally:
            os.unlink(temp_path)
    
    def test_file_exists(self):
        """测试文件存在检查"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test")
            temp_path = f.name
        
        try:
            reader = YamlFileReader()
            assert reader.file_exists(temp_path) is True
            assert reader.file_exists(temp_path + ".nonexistent") is False
        finally:
            os.unlink(temp_path)


class TestBaseDataLoader:
    """测试数据加载器基类"""
    
    def test_base_loader_initialization(self):
        """测试基础加载器初始化"""
        mock_reader = MockFileReader({})
        
        class TestLoader(BaseDataLoader):
            def load(self, identifier: str):
                return f"loaded:{identifier}"
        
        loader = TestLoader(mock_reader, "/test/dir")
        
        assert loader.file_reader is mock_reader
        assert loader.base_dir == "/test/dir"
        assert loader._logger is not None
    
    def test_get_file_path(self):
        """测试构建文件路径"""
        mock_reader = MockFileReader({})
        
        class TestLoader(BaseDataLoader):
            def load(self, identifier: str):
                pass
        
        loader = TestLoader(mock_reader, "/base/dir")
        
        path = loader._get_file_path("test", ".yaml")
        # 使用 os.path.join 来构建预期路径，确保跨平台兼容性
        expected = os.path.join("/base/dir", "test.yaml")
        assert path == expected
        
        path = loader._get_file_path("data", ".json")
        expected = os.path.join("/base/dir", "data.json")
        assert path == expected


class TestPersonaLoader:
    """测试人设加载器"""
    
    def test_load_persona_from_mock_data(self):
        """测试从模拟数据加载人设"""
        mock_yaml_data = {
            "name": "Test Character",
            "gender": "female",
            "age": 25,
            "identity": "adventurer",
            "background": {
                "education": "Guild training",
                "dreams": ["Explore ancient ruins"]
            },
            "personality": {
                "core_traits": ["brave", "curious"]
            },
            "emotion": {
                "default": "curious",
                "allowed": ["curious", "excited", "neutral"],
                "blocked": ["angry"],
                "intensity": 0.8,
                "material_package": "kaomoji_cute"
            }
        }
        
        mock_reader = MockFileReader({
            "/personas/test.yaml": mock_yaml_data
        })
        
        loader = PersonaLoader(mock_reader, "/personas")
        
        persona = loader.load("test")
        
        assert isinstance(persona, Persona)
        assert persona.name == "Test Character"
        assert "Test Character" in persona.system_prompt
        assert "female" in persona.system_prompt
        assert "adventurer" in persona.system_prompt
        
        assert persona.emotion_config.default_emotion == "curious"
        assert set(persona.emotion_config.allowed_emotions) == {"curious", "excited", "neutral"}
        assert persona.emotion_config.blocked_emotions == ["angry"]
        assert persona.emotion_config.expression_intensity == 0.8
        assert persona.emotion_config.material_package == "kaomoji_cute"
        
        assert persona.raw_data == mock_yaml_data
    
    def test_load_persona_file_not_found(self):
        """测试加载不存在的文件"""
        mock_reader = MockFileReader({})
        loader = PersonaLoader(mock_reader, "/personas")
        
        with pytest.raises(FileNotFoundError):
            loader.load("nonexistent")
    
    def test_persona_caching(self):
        """测试人设缓存"""
        mock_yaml_data = {"name": "Cached Character"}
        mock_reader = MockFileReader({"/personas/cached.yaml": mock_yaml_data})
        
        loader = PersonaLoader(mock_reader, "/personas")
        
        # 第一次加载
        persona1 = loader.load("cached")
        assert len(loader.get_cached_personas()) == 1
        
        # 第二次加载应返回缓存
        persona2 = loader.load("cached")
        assert persona1 is persona2  # 应该是同一个对象
        
        # 重新加载应清除缓存
        persona3 = loader.reload("cached")
        assert persona1 is not persona3  # 应该是新对象
        
        # 清除所有缓存
        loader.clear_cache()
        assert len(loader.get_cached_personas()) == 0
    
    @patch('os.path.exists')
    @patch('os.listdir')
    def test_load_all_personas(self, mock_listdir, mock_exists):
        """测试加载所有人设"""
        mock_reader = MockFileReader({
            "/personas/char1.yaml": {"name": "Character 1"},
            "/personas/char2.yaml": {"name": "Character 2"},
            "/personas/not_yaml.txt": {"name": "Should be ignored"}
        })
        
        loader = PersonaLoader(mock_reader, "/personas")
        
        # 模拟 os.path.exists 返回 True
        mock_exists.return_value = True
        # 模拟 os.listdir 返回文件列表
        mock_listdir.return_value = ["char1.yaml", "char2.yaml", "not_yaml.txt"]
        
        personas = loader.load_all()
        
        assert len(personas) == 2
        assert "char1" in personas
        assert "char2" in personas
        assert "not_yaml" not in personas
        
        assert personas["char1"].name == "Character 1"
        assert personas["char2"].name == "Character 2"


class TestWorldLoader:
    """测试世界观加载器"""
    
    def test_load_world_from_mock_data(self):
        """测试从模拟数据加载世界观"""
        mock_yaml_data = {
            "locations": [
                {
                    "name": "Town Square",
                    "description": "Central gathering place.",
                    "npcs": ["Mayor", "Merchant"],
                    "properties": {"weather": "sunny"}
                },
                {
                    "name": "Forest",
                    "description": "Dense forest.",
                    "npcs": ["Ranger"],
                    "properties": {"danger": "medium"}
                }
            ],
            "global_memories": [
                {
                    "content": "The town was founded 100 years ago.",
                    "priority": 8,
                    "tags": ["history", "town"]
                },
                "Simple memory string"
            ],
            "npcs": [
                {"name": "Blacksmith"},
                "Innkeeper"
            ]
        }
        
        mock_reader = MockFileReader({
            "/worlds/fantasy.yaml": mock_yaml_data
        })
        
        loader = WorldLoader(mock_reader, "/worlds")
        
        world = loader.load("fantasy")
        
        assert isinstance(world, WorldKnowledge)
        assert world.world_name == "fantasy"
        
        # 验证地点
        assert len(world.locations) == 2
        
        town_square = world.get_location("Town Square")
        assert town_square is not None
        assert town_square.description == "Central gathering place."
        # NPC列表可能包含从全局npcs字段添加的额外NPC
        assert "Mayor" in town_square.npcs
        assert "Merchant" in town_square.npcs
        assert town_square.get_property("weather") == "sunny"
        
        forest = world.get_location("Forest")
        assert forest is not None
        assert forest.description == "Dense forest."
        assert "Ranger" in forest.npcs
        assert forest.get_property("danger") == "medium"
        
        # 验证记忆
        assert len(world.global_memories) == 2
        
        # 验证NPC是否添加到默认地点
        # 由于有多个地点，NPC可能被添加到第一个地点
        assert "Blacksmith" in world.locations[0].npcs or "Innkeeper" in world.locations[0].npcs
    
    def test_load_world_file_not_found(self):
        """测试加载不存在的文件"""
        mock_reader = MockFileReader({})
        loader = WorldLoader(mock_reader, "/worlds")
        
        with pytest.raises(FileNotFoundError):
            loader.load("nonexistent")
    
    def test_create_default_world(self):
        """测试创建默认世界观"""
        mock_reader = MockFileReader({})
        loader = WorldLoader(mock_reader, "/worlds")
        
        world = loader.create_default_world()
        
        assert isinstance(world, WorldKnowledge)
        assert world.world_name == "Default World"
        assert len(world.locations) >= 1
        
        town_square = world.get_location("Town Square")
        assert town_square is not None
        assert "fountain" in town_square.description.lower() or "gathering" in town_square.description.lower()
    
    def test_world_caching(self):
        """测试世界观缓存"""
        mock_yaml_data = {"locations": []}
        mock_reader = MockFileReader({"/worlds/test.yaml": mock_yaml_data})
        
        loader = WorldLoader(mock_reader, "/worlds")
        
        # 第一次加载
        world1 = loader.load("test")
        assert len(loader.get_cached_worlds()) == 1
        
        # 第二次加载应返回缓存
        world2 = loader.load("test")
        assert world1 is world2  # 应该是同一个对象
        
        # 重新加载应清除缓存
        world3 = loader.reload("test")
        assert world1 is not world3  # 应该是新对象
        
        # 清除所有缓存
        loader.clear_cache()
        assert len(loader.get_cached_worlds()) == 0
    
    @patch('os.path.exists')
    @patch('os.listdir')
    def test_load_all_worlds(self, mock_listdir, mock_exists):
        """测试加载所有世界观"""
        mock_reader = MockFileReader({
            "/worlds/world1.yaml": {"locations": []},
            "/worlds/world2.json": {"locations": []},
            "/worlds/not_supported.txt": {"locations": []}
        })
        
        loader = WorldLoader(mock_reader, "/worlds")
        
        # 模拟 os.path.exists 返回 True
        mock_exists.return_value = True
        # 模拟 os.listdir 返回文件列表
        mock_listdir.return_value = ["world1.yaml", "world2.json", "not_supported.txt"]
        
        worlds = loader.load_all()
        
        assert len(worlds) == 2
        assert "world1" in worlds
        assert "world2" in worlds
        assert "not_supported" not in worlds


class TestIntegration:
    """集成测试"""
    
    def test_persona_and_session_integration(self):
        """测试人设和会话的集成"""
        from src.core.session import ConversationSession
        
        # 创建人设
        mock_yaml_data = {
            "name": "Integration Test Character",
            "emotion": {"default": "happy"}
        }
        
        mock_reader = MockFileReader({
            "/personas/integration.yaml": mock_yaml_data
        })
        
        persona_loader = PersonaLoader(mock_reader, "/personas")
        persona = persona_loader.load("integration")
        
        # 创建会话并绑定该人设
        session = ConversationSession(
            session_id="integration-test",
            bound_persona_file="integration.yaml"
        )
        
        assert session.bound_npc_id == "integration.yaml"
        
        # 验证人设的情绪配置会影响会话（未来扩展）
        # 目前只是文件名字符串绑定
    
    def test_world_and_memory_integration(self):
        """测试世界观和记忆的集成"""
        from src.core.types import MemoryItem
        
        # 创建世界观
        world = WorldKnowledge(world_name="Integration World")
        
        # 添加记忆
        memory = world.add_global_memory(
            content="Integration test memory",
            priority=9,
            tags=["test", "integration"]
        )
        
        assert isinstance(memory, MemoryItem)
        assert memory.memory_type == "world_global"
        assert memory.content == "Integration test memory"
        
        # 从世界观查询记忆
        results = world.query_memories("integration")
        assert len(results) == 1
        assert results[0] is memory


if __name__ == "__main__":
    pytest.main([__file__, "-v"])