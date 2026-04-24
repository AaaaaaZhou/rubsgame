# Tool Calling 功能开发手册

## 概述

本文档描述为 rubsgame 对话引擎添加 Tool Calling（工具调用）功能的设计与实现。核心目标是让 NPC 在对话过程中能够**主动检索世界观信息**（地点、游玩建议等）。

---

## 背景

当前架构中：
- `AssetManager.query_world(keyword)` 已存在，提供 RAG 可扩展接口
- `WorldKnowledge.query_locations()` / `query_memories()` 已实现
- LLM 仅作为对话模型，无法主动检索

需要新增：LLM 在对话过程中自主决定调用 `search_world` 工具查询世界观信息。

---

## 架构设计

### 工具定义

```python
# 工具名称
search_world

# 工具描述
当你想了解清溪镇的地点、活动或知识时调用，例如：哪里可以骑车？哪里适合看日落？夏天去哪玩？

# 参数
keyword: string  # 搜索关键词（地点名、活动类型、季节等）
```

### 工具结果格式

```json
{
  "locations": ["松林观景台", "桐子坡"],
  "memories": ["松林观景台位于城北山顶，是学生口碑最好的秘密地点..."]
}
```

### 核心流程

```
用户输入 → 构建 messages（含 tools schema）
    ↓
LLM 判断：回复内容 OR 调用 tool
    ↓
┌─ 直接回复 → 解析返回 → 输出
│
└─ tool_calls 触发 → 执行工具 → 将结果作为 tool result 追加到 messages
    ↓
LLM 再次推理（基于 tool 结果）
    ↓
最终回复
```

---

## 改动范围

| 文件 | 改动说明 |
|------|---------|
| `src/clients/base.py` | 基类增加 `chat_with_tools` 抽象方法 |
| `src/clients/openai_like.py` | 实现 tool 调用循环 |
| `src/core/engine.py` | 调用 `chat_with_tools`，注册 tools |

**不改动**：
- `src/core/orchestrator.py` — Prompt 组装逻辑不变
- `src/core/asset_manager.py` — `query_world` 已存在
- `src/core/world_model.py` — 数据模型不变

---

## 详细设计

### 1. 基类扩展 (`src/clients/base.py`)

新增抽象方法：

```python
def chat_with_tools(
    self,
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    **kwargs
) -> str:
    """发送对话请求，支持 tool calling

    Args:
        messages: 消息列表
        tools: OpenAI 格式的 tool schema 列表
        **kwargs: 额外参数

    Returns:
        模型最终回复文本
    """
    pass
```

### 2. OpenAI 兼容客户端 (`src/clients/openai_like.py`)

#### 2.1 增加 tools 参数支持

在 `_build_base_params` 中增加：

```python
if tools:
    params["tools"] = tools
```

#### 2.2 实现 tool 调用循环

核心逻辑：

```python
def chat_with_tools(
    self,
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    **kwargs
) -> str:
    request_params = self._build_base_params(messages, **kwargs)
    if tools:
        request_params["tools"] = tools

    max_iterations = 10  # 防止无限循环
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        response = self._client.chat.completions.create(**request_params)
        message = response.choices[0].message

        # 情况1：直接回复，结束
        if not message.tool_calls:
            return message.content or ""

        # 情况2：执行 tool 调用
        for tool_call in message.tool_calls:
            tool_result = self._execute_tool(tool_call.function, tools)
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": tool_call.id,
                    "type": "function",
                    "function": tool_call.function
                }]
            })
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result
            })

        # 继续循环，让 LLM 基于结果生成回复

    raise RuntimeError("Tool calling exceeded max iterations")
```

#### 2.3 工具执行方法

```python
def _execute_tool(
    self,
    function: Function,
    tools: List[Dict[str, Any]]
) -> str:
    """根据 function name 执行对应工具"""
    tool_map = {t["function"]["name"]: t for t in tools}
    func_name = function.name

    if func_name == "search_world":
        import json
        args = json.loads(function.arguments)
        # 调用 asset_manager.query_world
        # 注意：需要传入 asset_manager 引用
        result = self._asset_manager.query_world(args["keyword"])
        return json.dumps(result, ensure_ascii=False)

    raise ValueError(f"Unknown tool: {func_name}")
```

**问题**：`OpenAILikeClient` 目前没有 `asset_manager` 引用。需要通过参数传入或使用全局单例。

**解决方案**：在 `ClientManager` 中持有 `asset_manager` 引用，`chat_with_tools` 调用时自动注入。

### 3. 客户端管理器改造 (`src/clients/manager.py`)

```python
def get_client(...):  # 不变

def get_client_with_asset_manager(self, asset_manager) -> BaseLLMClient:
    """获取支持 tool 的客户端实例"""
    client = self.get_client()
    client.set_asset_manager(asset_manager)
    return client
```

### 4. 引擎集成 (`src/core/engine.py`)

#### 4.1 定义 tool schema

在 `EngineCore` 中定义：

```python
WORLD_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_world",
            "description": "当你想了解清溪镇的地点、活动或知识时调用，例如：哪里可以骑车？哪里适合看日落？夏天去哪玩？",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词，可以是地点名称、活动类型、季节特征等"
                    }
                },
                "required": ["keyword"]
            }
        }
    }
]
```

#### 4.2 改造 chat() 方法

```python
def chat(self, user_input: str, session_id: str = "default") -> Dict[str, Any]:
    session = self.get_or_create_session(session_id)
    messages = self._orchestrator.build_messages(session, user_input)

    # 调用支持 tool 的客户端
    client = self._client_mgr.get_client_with_asset_manager(self._asset_mgr)
    response_text = client.chat_with_tools(
        messages,
        tools=self.WORLD_TOOLS
    )

    parsed = self._parse_response(response_text)
    session.add_message("user", user_input)
    session.add_message("assistant", parsed["content"])

    return {
        "content": parsed["content"],
        "emotion": parsed["emotion"],
        "intensity": parsed["intensity"],
        "session_id": session_id
    }
```

---

## 消息格式示例

### 首次请求（含 tools）

```json
{
  "model": "deepseek-reasoner",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "周末去哪玩好呢？"}
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "search_world",
        "description": "...",
        "parameters": {...}
      }
    }
  ],
  "tool_choice": "auto"
}
```

### Tool Call 响应

```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": null,
      "tool_calls": [{
        "id": "call_abc123",
        "type": "function",
        "function": {
          "name": "search_world",
          "arguments": "{\"keyword\": \"适合看日落的地方\"}"
        }
      }]
    }
  }]
}
```

### Tool Result 追加到消息

```json
{
  "role": "tool",
  "tool_call_id": "call_abc123",
  "content": "{\"locations\": [\"松林观景台\", \"桐子坡\"], \"memories\": [...]}"
}
```

### 最终请求（含 tool 结果）

```json
{
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "周末去哪玩好呢？"},
    {"role": "assistant", "content": null, "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "call_abc123", "content": "..."}
  ],
  "tools": [...]
}
```

---

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| Tool 执行失败 | 返回错误信息字符串给 LLM，让其决定如何回复 |
| 无限循环（>10次） | 抛出 RuntimeError |
| Tool schema 不匹配 | 跳过该 tool_call，继续 |
| 未知 tool name | 记录警告，返回错误信息 |

---

## 测试策略

### 单元测试

1. **客户端测试** (`unittest/llm/test_connection.py`)
   - 测试 `chat_with_tools` 方法存在性
   - 测试 tool schema 正确传递
   - 测试 tool 调用循环

2. **引擎测试** (`unittest/core/test_engine.py`) — 新建
   - 测试 tool 注册
   - 测试对话流程

### 集成测试

手动测试场景：
1. 问"周末去哪玩" → 触发 search_world
2. 问"清溪峡怎么玩" → 直接回答（不需要 tool）
3. 连续两次触发 tool

---

## 实施步骤

1. [ ] 在 `src/clients/base.py` 添加 `chat_with_tools` 抽象方法
2. [ ] 在 `src/clients/openai_like.py` 实现 tool 调用循环
3. [ ] 在 `src/clients/manager.py` 添加 `get_client_with_asset_manager` 方法
4. [ ] 在 `src/core/engine.py` 集成 tool calling
5. [ ] 更新单元测试
6. [ ] 运行所有测试确保通过

---

## 附录：OpenAI Tool Calling 文档参考

- Tool schema 格式：https://platform.openai.com/docs/guides/function-calling
- `tool_calls` 对象结构：
  - `id`: 唯一标识
  - `type`: 固定为 "function"
  - `function`: { "name": str, "arguments": json_string }
- `tool_choice`: "auto" | "none" | 具体 tool 名
