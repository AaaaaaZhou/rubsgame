# 记忆系统设计文档

## 1. 概述

记忆系统是 rubsgame 对话引擎的核心组件，负责管理对话历史的压缩（精炼）和重要信息的提取（记忆抽取）。当对话变长时，Token 消耗持续增长，记忆系统通过平衡策略保持对话效率同时保留关键信息。

### 1.1 核心能力

- **历史精炼**：将过长的对话历史压缩为摘要 + 最近对话的组合
- **记忆提取**：从对话中提取结构化记忆，分类为会话级或全局世界观级
- **统一调度**：MemoryManager 协调精炼和提取的触发时机和处理流程

---

## 2. 架构

```
EngineCore.finalize_and_save()
        │
        ▼
MemoryManager.refine_and_extract()
        │
        ├──────────────────────────────┐
        ▼                              ▼
BalancedHistoryRefiner          LLMMemoryExtractor
        │                              │
        ▼                              ▼
refined_history 更新          session_memories (local)
                                   │
                          update_global_memory() (world)
```

---

## 3. 核心组件

### 3.1 MemoryConfig

配置入口，通过 `AppConfig.get_memory_config()` 获取 YAML 中的配置。

```python
@dataclass
class MemoryConfig:
    refine_threshold_tokens: int = 4000   # Token 超限阈值
    refine_max_turns: int = 20             # 轮次超限阈值
    extraction_interval: int = 10          # 提取间隔（轮次）
    extractor_llm_model: str = "deepseek_reasoner"
    max_memories_per_extraction: int = 5
    memory_priority_threshold: int = 5
    max_session_memories: int = 20
    max_world_memories: int = 50
    balance_strategy: BalanceStrategyConfig
```

### 3.2 BalancedHistoryRefiner

平衡策略精炼器，压缩逻辑：

```
full_history: [S, U1, A1, U2, A2, ..., U20, A20]
                    │
           BalancedHistoryRefiner
                    │
    ┌───────────────┼───────────────┐
    ▼               ▼               ▼
[S, ...]      [摘要消息]     [U(N-10), A(N-10), ..., U(N), A(N)]
(保留系统头)     (中间压缩)        (保留最近10轮)
```

方法：
- `refine(session, config)` — 使用占位符摘要压缩中间
- `refine_with_summary(session, config, llm_summary)` — 使用 LLM 真实摘要压缩

### 3.3 LLMMemoryExtractor

基于 LLM 的记忆提取器，从 full_history 提取结构化记忆。

**输出格式**：
```json
[
  {
    "content": "记忆内容（简洁描述）",
    "memory_type": "session_local" 或 "world_global",
    "priority": 0-10,
    "tags": ["标签1", "标签2"]
  }
]
```

**处理流程**：
- `session_local` → `session.session_memories`
- `world_global` → `AssetManager.update_global_memory()`

### 3.4 MemoryManager

统一调度器，协调精炼和提取流程。

主要方法：
- `refine_and_extract(session, force=False)` — 主调度方法
- `_should_trigger(session)` — 检查 Token/轮次阈值
- `trigger_extraction(session)` — 手动触发提取（退出时用）

---

## 4. 触发时机

| 触发条件 | 行为 |
|---------|------|
| Token ≥ 4000（可配置） | 触发精炼 + 提取 |
| 轮次 ≥ 20（可配置） | 触发精炼 + 提取 |
| 会话退出（finalize_and_save） | 强制精炼 + 最终提取 |

---

## 5. 配置

在 `config/settings.yaml` 中配置：

```yaml
memory:
  refine_threshold_tokens: 4000    # Token 超限阈值
  refine_max_turns: 20            # 对话轮次超限阈值
  extraction_interval: 10         # 记忆提取间隔（轮次）
  extractor_llm_model: "deepseek_reasoner"
  max_memories_per_extraction: 5
  memory_priority_threshold: 5
  max_session_memories: 20
  max_world_memories: 50
  balance_strategy:
    keep_recent_turns: 10
    keep_system: true
    compress_middle: true
```

---

## 6. 扩展点

### 6.1 自定义精炼器

继承 `BaseHistoryRefiner`：

```python
class CustomRefiner(BaseHistoryRefiner):
    def refine(self, session, config):
        # 实现自定义精炼逻辑
        pass
```

### 6.2 自定义提取器

继承 `BaseMemoryExtractor`：

```python
class CustomExtractor(BaseMemoryExtractor):
    def extract(self, session, llm_client, config):
        # 实现自定义提取逻辑
        return memories
```

注册到 MemoryManager：
```python
memory_mgr = MemoryManager()
memory_mgr._extractor = CustomExtractor()
```

---

## 7. 文件结构

```
src/core/memory/
├── __init__.py          # 模块导出
├── config.py            # MemoryConfig, BalanceStrategyConfig
├── refiner.py           # BaseHistoryRefiner, BalancedHistoryRefiner
├── extractor.py         # BaseMemoryExtractor, LLMMemoryExtractor, RuleBasedMemoryExtractor
└── memory_manager.py    # MemoryManager
```