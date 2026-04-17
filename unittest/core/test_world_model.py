"""
世界观数据模型测试
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import pytest
from core.world_model import Location, WorldKnowledge
from core.session import MemoryItem


class TestLocation:
    """测试Location类"""
    
    def test_location_creation(self):
        """测试地点创建"""
        location = Location(
            name="Town Square",
            description="The central square of the town.",
            npcs=["Merchant", "Guard"],
            properties={"weather": "sunny", "crowded": True}
        )
        
        assert location.name == "Town Square"
        assert location.description == "The central square of the town."
        assert location.npcs == ["Merchant", "Guard"]
        assert location.properties["weather"] == "sunny"
        assert location.properties["crowded"] is True
    
    def test_location_defaults(self):
        """测试地点默认值"""
        location = Location(name="Tavern", description="A cozy tavern.")
        
        assert location.name == "Tavern"
        assert location.description == "A cozy tavern."
        assert location.npcs == []
        assert location.properties == {}
    
    def test_add_npc(self):
        """测试添加NPC"""
        location = Location(name="Market", description="Busy market.")
        
        location.add_npc("Vendor")
        assert "Vendor" in location.npcs
        
        # 测试去重
        location.add_npc("Vendor")
        assert location.npcs.count("Vendor") == 1
        
        location.add_npc("Customer")
        assert set(location.npcs) == {"Vendor", "Customer"}
    
    def test_remove_npc(self):
        """测试移除NPC"""
        location = Location(
            name="Castle",
            description="Royal castle.",
            npcs=["King", "Queen", "Guard"]
        )
        
        # 移除存在的NPC
        result = location.remove_npc("Queen")
        assert result is True
        assert "Queen" not in location.npcs
        assert len(location.npcs) == 2
        
        # 移除不存在的NPC
        result = location.remove_npc("Wizard")
        assert result is False
        assert len(location.npcs) == 2
    
    def test_set_and_get_property(self):
        """测试设置和获取属性"""
        location = Location(name="Forest", description="Mysterious forest.")
        
        location.set_property("danger_level", "high")
        location.set_property("creatures", ["elves", "fairies"])
        
        assert location.get_property("danger_level") == "high"
        assert location.get_property("creatures") == ["elves", "fairies"]
        assert location.get_property("non_existent") is None
        assert location.get_property("non_existent", "default") == "default"
    
    def test_location_to_dict(self):
        """测试地点序列化"""
        location = Location(
            name="Library",
            description="Ancient library.",
            npcs=["Librarian"],
            properties={"quiet": True, "books": 1000}
        )
        
        data = location.to_dict()
        
        assert data["name"] == "Library"
        assert data["description"] == "Ancient library."
        assert data["npcs"] == ["Librarian"]
        assert data["properties"]["quiet"] is True
        assert data["properties"]["books"] == 1000
    
    def test_location_from_dict(self):
        """测试地点反序列化"""
        original = Location(
            name="Workshop",
            description="Blacksmith's workshop.",
            npcs=["Blacksmith", "Apprentice"],
            properties={"temperature": "hot", "tools": ["hammer", "anvil"]}
        )
        
        data = original.to_dict()
        restored = Location.from_dict(data)
        
        assert restored.name == original.name
        assert restored.description == original.description
        assert restored.npcs == original.npcs
        assert restored.properties == original.properties
    
    def test_location_str(self):
        """测试地点字符串表示"""
        location = Location(name="Temple", description="Holy temple.", npcs=["Priest", "Acolyte"])
        
        str_repr = str(location)
        assert "Temple" in str_repr
        assert "npcs=2" in str_repr


class TestWorldKnowledge:
    """测试WorldKnowledge类"""
    
    def test_world_creation(self):
        """测试世界观创建"""
        world = WorldKnowledge(world_name="Fantasy Land")
        
        assert world.world_name == "Fantasy Land"
        assert world.locations == []
        assert world.global_memories == []
    
    def test_add_location(self):
        """测试添加地点"""
        world = WorldKnowledge(world_name="Test World")
        
        location1 = Location(name="Village", description="Small village.")
        location2 = Location(name="Forest", description="Dark forest.")
        
        world.add_location(location1)
        world.add_location(location2)
        
        assert len(world.locations) == 2
        assert world.locations[0].name == "Village"
        assert world.locations[1].name == "Forest"
    
    def test_add_duplicate_location(self):
        """测试添加重复地点（应更新）"""
        world = WorldKnowledge(world_name="Test World")
        
        location1 = Location(name="City", description="Old description.")
        location2 = Location(name="City", description="New description.", npcs=["Mayor"])
        
        world.add_location(location1)
        world.add_location(location2)  # 应更新现有地点
        
        assert len(world.locations) == 1
        assert world.locations[0].description == "New description."
        assert world.locations[0].npcs == ["Mayor"]
    
    def test_get_location(self):
        """测试获取地点"""
        world = WorldKnowledge(world_name="Test World")
        
        village = Location(name="Village", description="A village.")
        forest = Location(name="Forest", description="A forest.")
        
        world.add_location(village)
        world.add_location(forest)
        
        # 获取存在的地点
        found = world.get_location("Village")
        assert found is not None
        assert found.name == "Village"
        
        # 获取不存在的地点
        not_found = world.get_location("Mountain")
        assert not_found is None
    
    def test_add_global_memory(self):
        """测试添加全局记忆"""
        world = WorldKnowledge(world_name="Test World")
        
        memory = world.add_global_memory(
            content="The king is wise and just.",
            priority=8,
            tags=["king", "royalty"]
        )
        
        assert isinstance(memory, MemoryItem)
        assert memory.content == "The king is wise and just."
        assert memory.memory_type == "world_global"
        assert memory.priority == 8
        assert memory.tags == ["king", "royalty"]
        
        assert len(world.global_memories) == 1
        assert world.global_memories[0] == memory
    
    def test_add_duplicate_memory(self):
        """测试添加重复记忆（基于内容去重）"""
        world = WorldKnowledge(world_name="Test World")
        
        memory1 = world.add_global_memory("Same content", priority=5)
        memory2 = world.add_global_memory("Same content", priority=9)  # 应返回已存在的记忆
        
        assert memory1 is memory2  # 应该是同一个对象
        assert len(world.global_memories) == 1
        assert world.global_memories[0].priority == 5  # 保持原始优先级
    
    def test_add_existing_memory(self):
        """测试添加已存在的记忆项"""
        world = WorldKnowledge(world_name="Test World")
        
        existing_memory = MemoryItem(
            content="Ancient prophecy",
            memory_type="world_global",
            priority=10,
            tags=["prophecy", "ancient"]
        )
        
        world.add_existing_memory(existing_memory)
        
        assert len(world.global_memories) == 1
        assert world.global_memories[0] is existing_memory
    
    def test_get_system_context(self):
        """测试获取系统上下文"""
        world = WorldKnowledge(world_name="Fantasy Kingdom")
        
        # 空世界观
        context = world.get_system_context()
        assert "Fantasy Kingdom" in context
        assert "Locations:" not in context
        
        # 添加地点
        world.add_location(Location(
            name="Capital City",
            description="The bustling capital of the kingdom.",
            npcs=["King", "Merchants"]
        ))
        
        world.add_location(Location(
            name="Dark Forest",
            description="A dangerous forest full of mysteries."
        ))
        
        # 添加重要记忆
        world.add_global_memory("The kingdom is at peace.", priority=9)
        world.add_global_memory("A dragon lives in the mountains.", priority=7)
        world.add_global_memory("Minor detail.", priority=3)  # 不重要，不会显示
        
        context = world.get_system_context()
        
        assert "Fantasy Kingdom" in context
        assert "Capital City" in context
        assert "Dark Forest" in context
        assert "King" in context or "Merchants" in context
        assert "The kingdom is at peace." in context
        assert "A dragon lives in the mountains." in context
        assert "Minor detail." not in context  # 优先级太低
    
    def test_query_locations(self):
        """测试查询地点"""
        world = WorldKnowledge(world_name="Test World")
        
        world.add_location(Location(
            name="Silver Lake",
            description="A beautiful silver lake."
        ))
        
        world.add_location(Location(
            name="Golden Mountain",
            description="A mountain with golden peaks."
        ))
        
        world.add_location(Location(
            name="Forest of Shadows",
            description="A dark and shadowy forest."
        ))
        
        # 查询匹配的地点
        results = world.query_locations("silver")
        assert len(results) == 1
        assert results[0].name == "Silver Lake"
        
        results = world.query_locations("golden")
        assert len(results) == 1
        assert results[0].name == "Golden Mountain"
        
        results = world.query_locations("forest")
        assert len(results) == 1
        assert results[0].name == "Forest of Shadows"
        
        results = world.query_locations("mountain")
        assert len(results) == 1
        assert results[0].name == "Golden Mountain"
        
        # 查询无结果
        results = world.query_locations("ocean")
        assert len(results) == 0
    
    def test_query_memories(self):
        """测试查询记忆"""
        world = WorldKnowledge(world_name="Test World")
        
        world.add_global_memory("The wizard knows many spells.", priority=5)
        world.add_global_memory("The knight is brave and strong.", priority=5)
        world.add_global_memory("Spells can be dangerous.", priority=5)
        
        results = world.query_memories("wizard")
        assert len(results) == 1
        assert "wizard" in results[0].content.lower()
        
        results = world.query_memories("spells")
        assert len(results) == 2  # 两条记忆包含"spells"
        
        results = world.query_memories("dragon")
        assert len(results) == 0
    
    def test_world_to_dict(self):
        """测试世界观序列化"""
        world = WorldKnowledge(world_name="Test World")
        
        world.add_location(Location(name="Town", description="A small town."))
        world.add_global_memory("Test memory.", priority=5)
        
        data = world.to_dict()
        
        assert data["world_name"] == "Test World"
        assert len(data["locations"]) == 1
        assert len(data["global_memories"]) == 1
        assert data["locations"][0]["name"] == "Town"
        assert data["global_memories"][0]["content"] == "Test memory."
    
    def test_world_from_dict(self):
        """测试世界观反序列化"""
        original = WorldKnowledge(world_name="Original World")
        
        original.add_location(Location(name="City", description="Big city."))
        original.add_location(Location(name="River", description="Flowing river."))
        original.add_global_memory("Memory 1", priority=7)
        original.add_global_memory("Memory 2", priority=3)
        
        data = original.to_dict()
        restored = WorldKnowledge.from_dict(data)
        
        assert restored.world_name == original.world_name
        assert len(restored.locations) == len(original.locations)
        assert len(restored.global_memories) == len(original.global_memories)
        
        # 验证地点名称
        restored_names = [loc.name for loc in restored.locations]
        original_names = [loc.name for loc in original.locations]
        assert set(restored_names) == set(original_names)
    
    def test_get_statistics(self):
        """测试获取统计信息"""
        world = WorldKnowledge(world_name="Statistics World")
        
        # 空世界观
        stats = world.get_statistics()
        assert stats["world_name"] == "Statistics World"
        assert stats["location_count"] == 0
        assert stats["memory_count"] == 0
        assert stats["total_npcs"] == 0
        assert stats["avg_memory_priority"] == 0
        
        # 添加数据
        world.add_location(Location(
            name="Location 1",
            description="Desc 1",
            npcs=["NPC1", "NPC2"]
        ))
        
        world.add_location(Location(
            name="Location 2",
            description="Desc 2",
            npcs=["NPC3"]
        ))
        
        world.add_global_memory("Memory 1", priority=8)
        world.add_global_memory("Memory 2", priority=4)
        world.add_global_memory("Memory 3", priority=6)
        
        stats = world.get_statistics()
        
        assert stats["location_count"] == 2
        assert stats["memory_count"] == 3
        assert stats["total_npcs"] == 3
        assert stats["avg_memory_priority"] == (8 + 4 + 6) / 3
    
    def test_world_str_repr(self):
        """测试世界观字符串表示"""
        world = WorldKnowledge(world_name="My World")
        
        world.add_location(Location(name="Place", description="A place."))
        world.add_global_memory("Something important.", priority=5)
        
        str_repr = str(world)
        assert "My World" in str_repr
        assert "locations=1" in str_repr
        assert "memories=1" in str_repr
        
        repr_repr = repr(world)
        assert "WorldKnowledge" in repr_repr
        assert "My World" in repr_repr


if __name__ == "__main__":
    pytest.main([__file__, "-v"])