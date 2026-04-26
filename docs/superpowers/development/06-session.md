# Session 扩展开发指南

## 概述

为 ConversationSession 增加视觉小说模式所需的字段，并确保这些字段能正确持久化。

## 需要扩展的字段

```python
# ConversationSession 新增字段

@dataclass
class ConversationSession:
    # === 现有字段 ===
    session_id: str
    bound_npc_id: str
    full_history: List[Message] = field(default_factory=list)
    refined_history: List[Message] = field(default_factory=list)
    session_memories: List[MemoryItem] = field(default_factory=list)
    # ... 其他现有字段

    # === 新增字段 ===

    # 剧情状态
    plot_state: PlotState = field(default_factory=PlotState)

    # 对话选项相关
    last_option_turn: int = 0
    option_pending: Optional[DialogOption] = None
    npc_suggestion_pending: Optional[dict] = None

    # NPC交互相关
    npc_interaction_queue: List[NPCInteraction] = field(default_factory=list)
    active_npc_interaction: Optional[NPCInteraction] = None
    npc_relationships: Dict[str, int] = field(default_factory=dict)

    # 位置
    current_location: Optional[str] = None

    # 情绪追踪
    last_emotion: str = "neutral"
    last_emotion_intensity: float = 0.5
```

## PlotState 定义

```python
# src/core/plot/types.py 中已定义

@dataclass
class PlotState:
    chapter_id: str = ""
    node_id: str = ""
    is_exploring: bool = True
    is_branch_point: bool = False
    queued_narrative: Optional[str] = None
```

## 持久化扩展

### SessionManager 保存逻辑

```python
# src/core/session_manager.py 修改

class SessionManager:
    def save_session(self, session: ConversationSession) -> None:
        """保存会话"""
        session_path = self._get_session_path(session.session_id)

        data = {
            "session_id": session.session_id,
            "bound_npc_id": session.bound_npc_id,
            "full_history": [msg.to_dict() for msg in session.full_history],
            "refined_history": [msg.to_dict() for msg in session.refined_history],
            "session_memories": [mem.to_dict() for mem in session.session_memories],

            # 新增字段
            "plot_state": {
                "chapter_id": session.plot_state.chapter_id,
                "node_id": session.plot_state.node_id,
                "is_exploring": session.plot_state.is_exploring,
                "is_branch_point": session.plot_state.is_branch_point,
                "queued_narrative": session.plot_state.queued_narrative
            },
            "last_option_turn": session.last_option_turn,
            "option_pending": session.option_pending.to_dict() if session.option_pending else None,
            "npc_suggestion_pending": session.npc_suggestion_pending,
            "npc_relationships": session.npc_relationships,
            "current_location": session.current_location,
            "last_emotion": session.last_emotion,
            "last_emotion_intensity": session.last_emotion_intensity
        }

        with open(session_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        _logger.debug(f"Session saved: {session.session_id}")
```

### SessionManager 加载逻辑

```python
    def _load_session(self, session_id: str) -> Optional[ConversationSession]:
        """从文件加载会话"""
        session_path = self._get_session_path(session_id)
        if not session_path.exists():
            return None

        with open(session_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 解析 plot_state
        plot_state_data = data.get("plot_state", {})
        plot_state = PlotState(
            chapter_id=plot_state_data.get("chapter_id", ""),
            node_id=plot_state_data.get("node_id", ""),
            is_exploring=plot_state_data.get("is_exploring", True),
            is_branch_point=plot_state_data.get("is_branch_point", False),
            queued_narrative=plot_state_data.get("queued_narrative")
        )

        # 解析 option_pending
        option_data = data.get("option_pending")
        option_pending = None
        if option_data:
            option_pending = DialogOption(
                type=OptionType(option_data.get("type", "fixed")),
                content=option_data.get("content", ""),
                action=option_data.get("action"),
                target=option_data.get("target")
            )

        # 解析 npc_interaction_queue（简化，实际需要完整重构）
        npc_queue_data = data.get("npc_interaction_queue", [])
        npc_queue = []
        # TODO: 实现完整的 NPCInteraction 反序列化

        session = ConversationSession(
            session_id=data["session_id"],
            bound_npc_id=data.get("bound_npc_id", ""),
            full_history=[Message(**m) for m in data.get("full_history", [])],
            refined_history=[Message(**m) for m in data.get("refined_history", [])],
            session_memories=[MemoryItem(**m) for m in data.get("session_memories", [])],

            # 新增字段
            plot_state=plot_state,
            last_option_turn=data.get("last_option_turn", 0),
            option_pending=option_pending,
            npc_suggestion_pending=data.get("npc_suggestion_pending"),
            npc_interaction_queue=npc_queue,
            active_npc_interaction=None,
            npc_relationships=data.get("npc_relationships", {}),
            current_location=data.get("current_location"),
            last_emotion=data.get("last_emotion", "neutral"),
            last_emotion_intensity=data.get("last_emotion_intensity", 0.5)
        )

        return session
```

## 数据迁移

首次加载旧版本 session 文件时，新字段使用默认值：

```python
def _migrate_session_data(self, data: dict) -> dict:
    """迁移旧版本session数据"""
    defaults = {
        "plot_state": {
            "chapter_id": "",
            "node_id": "",
            "is_exploring": True,
            "is_branch_point": False,
            "queued_narrative": None
        },
        "last_option_turn": 0,
        "option_pending": None,
        "npc_suggestion_pending": None,
        "npc_interaction_queue": [],
        "npc_relationships": {},
        "current_location": None,
        "last_emotion": "neutral",
        "last_emotion_intensity": 0.5
    }

    for key, value in defaults.items():
        if key not in data:
            data[key] = value

    return data
```

## Session 创建修改

当创建新会话时：

```python
# src/core/session_manager.py
def create_session(self, session_id: str, npc_id: str = "") -> ConversationSession:
    """创建新会话"""
    session = ConversationSession(
        session_id=session_id,
        bound_npc_id=npc_id,
        plot_state=PlotState(),  # 新增
        npc_relationships={},    # 新增
        # ...
    )
    self._sessions[session_id] = session
    return session
```

## Session.to_dict() 扩展

如果 ConversationSession 有 to_dict 方法，也需要更新：

```python
# 如果需要序列化方法
def to_dict(self) -> dict:
    return {
        "session_id": self.session_id,
        "bound_npc_id": self.bound_npc_id,
        # ... 其他字段
        "plot_state": {
            "chapter_id": self.plot_state.chapter_id,
            "node_id": self.plot_state.node_id,
            "is_exploring": self.plot_state.is_exploring,
            "is_branch_point": self.plot_state.is_branch_point,
            "queued_narrative": self.plot_state.queued_narrative
        },
        # ...
    }
```

## 测试用例

```python
# unittest/core/plot/test_session.py
import pytest
import json
import tempfile
from pathlib import Path
from src.core.session_manager import SessionManager
from src.core.session import ConversationSession
from src.core.plot.types import PlotState


class TestSessionPersistence:
    def test_save_and_load_session_with_plot_state(self, tmp_path):
        manager = SessionManager(str(tmp_path))

        session = manager.create_session("test_session", "alice")
        session.plot_state.chapter_id = "chapter_01"
        session.plot_state.node_id = "n1"
        session.plot_state.is_exploring = False
        session.current_location = "咖啡馆"
        session.npc_relationships = {"alice": 50}

        manager.save_session(session)

        # 重新加载
        loaded = manager.get_session("test_session")
        assert loaded is not None
        assert loaded.plot_state.chapter_id == "chapter_01"
        assert loaded.plot_state.node_id == "n1"
        assert loaded.current_location == "咖啡馆"
        assert loaded.npc_relationships["alice"] == 50

    def test_migration_old_session_format(self, tmp_path):
        """测试旧版本session文件的迁移"""
        session_file = tmp_path / "old_session.json"
        session_file.write_text(json.dumps({
            "session_id": "old_session",
            "bound_npc_id": "alice",
            "full_history": [],
            "refined_history": [],
            "session_memories": []
        }))

        manager = SessionManager(str(tmp_path))
        loaded = manager.get_session("old_session")

        # 新字段应该使用默认值
        assert loaded.plot_state.chapter_id == ""
        assert loaded.plot_state.is_exploring == True
        assert loaded.last_option_turn == 0
```
