# 开发者指南：扩展记忆系统

## 1. 添加自定义精炼策略

### 1.1 实现抽象基类

```python
from src.core.memory.refiner import BaseHistoryRefiner, MemoryConfig

class AggressiveRefiner(BaseHistoryRefiner):
    """极致压缩策略：只保留最近5轮和系统消息"""

    def refine(self, session: ConversationSession, config: MemoryConfig) -> None:
        # 获取系统消息
        system_msgs = [m for m in session.full_history if m.role == "system"]
        # 获取最近5轮对话
        dialog_msgs = [m for m in session.full_history if m.role != "system"]
        keep_recent = dialog_msgs[-10:]  # 最近5轮 = 10条消息

        # 更新
        session.refined_history = system_msgs[:1] + keep_recent
```

### 1.2 注册和使用

```python
from src.core.memory import MemoryManager

memory_mgr = MemoryManager()
memory_mgr._refiner = AggressiveRefiner()
```

---

## 2. 添加自定义提取器

### 2.1 实现抽象基类

```python
from src.core.memory.extractor import BaseMemoryExtractor, MemoryConfig

class KeywordMemoryExtractor(BaseMemoryExtractor):
    """基于关键词的记忆提取器"""

    def __init__(self):
        self._keywords = ["重要", "记住", "决定", "任务", "喜欢"]

    def extract(self, session, llm_client=None, config=None):
        memories = []
        for msg in session.full_history:
            for keyword in self._keywords:
                if keyword in msg.content:
                    memories.append(MemoryItem(
                        content=msg.content[:200],
                        memory_type="session_local",
                        priority=7,
                        tags=["keyword", keyword]
                    ))
        return memories
```

### 2.2 注册和使用

```python
memory_mgr = MemoryManager()
memory_mgr._extractor = KeywordMemoryExtractor()
```

---

## 3. 配置多个模型

可以在 `config/llm_config.yaml` 中配置多个提取模型：

```yaml
models:
  deepseek_reasoner:
    api_key: "..."
    # 用于主对话

  # 用于记忆提取的小型模型
  llama3.2:
    api_key: ""
    base_url: "http://localhost:11434/v1"
    model: "llama3.2"
```

在 `config/settings.yaml` 中指定提取模型：

```yaml
memory:
  extractor_llm_model: "llama3.2"
```

---

## 4. 调试技巧

### 4.1 查看精炼效果

在 `data/sessions/default.json` 中检查 `refined_history`：

```json
{
  "session_id": "default",
  "refined_history": [
    {"role": "system", "content": "[World] ..."},
    {"role": "system", "content": "[对话摘要] ...", "metadata": {"is_summary": true}},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

### 4.2 查看提取的记忆

在同一个会话文件中检查 `session_memories`：

```json
{
  "session_memories": [
    {
      "content": "玩家帮助NPC找到了钥匙",
      "memory_type": "session_local",
      "priority": 7,
      "tags": ["event", "quest"]
    }
  ]
}
```

### 4.3 强制触发精炼

```python
from src.core.engine import EngineCore

engine = EngineCore()
memory_mgr = engine._get_memory_manager()

session = engine.get_or_create_session("test")
result = memory_mgr.refine_and_extract(session, force=True)
print(result)
```

---

## 5. 性能优化建议

1. **调整提取间隔**：如果 Token 充足，可以增大 `extraction_interval` 减少 LLM 调用
2. **使用小型模型**：对于记忆提取，可以使用 llama3.2 等小型本地模型
3. **调整优先级阈值**：增大 `memory_priority_threshold` 可减少提取的记忆数量
4. **限制历史长度**：在 `balance_strategy.keep_recent_turns` 中调整保留轮数