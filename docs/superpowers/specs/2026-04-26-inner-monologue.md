# 内心旁白模块设计

## 1. 概述

为 NarratorGenerator 新增 **INNER_MONOLOGUE** 类型旁白，支持 NPC 心理活动描写，采用非确定性叙事风格。

## 2. NarrativeContext 枚举变更

```python
class NarrativeContext(Enum):
    SCENE_ENTER      # 进入新场景
    SCENE_EXIT       # 离开场景
    EMOTION_BUILD    # 情绪铺垫
    TRANSITION       # 剧情过渡（时间/地点跳跃）
    ACTION_RESULT    # 行动结果描述
    CHAPTER_START    # 章节开始
    CHAPTER_END      # 章节结束
    FREE_EXPLORE     # 自由探索状态描述
    INNER_MONOLOGUE  # NPC心理活动描写（新增）
```

## 3. 触发时机

| Context | 触发时机 | 来源 |
|---------|---------|------|
| INNER_MONOLOGUE | NPC主动交互触发时 | NPCInteractionManager 生成交互内容前 |

## 4. Prompt 模板

```
[System]
当前旁白类型：{narrative_context}
当前场景：{location}
当前情绪基调：{emotion}（{style}）
主线进度：{chapter_name} - {node_id}

请生成一段 NPC {npc_name} 的心理活动描写。
要求：
- 从NPC视角描写其内心状态
- 使用模糊/非确定性措辞（如"似乎"、"也许"、"隐约感到"）
- 长度为1-2句话
```

## 5. 叙事风格约束

**减少使用确定性措辞**，使用模糊/非确定性表达：
- good: "似乎"、"也许"、"隐约感到"、"好像"、"似乎在想着"
- not so good: "确定地"、"清楚地知道"、"毫无疑问"

## 6. 与其他模块的配合

### 6.1 与 NPCInteractionManager 配合

```python
# NPCInteractionManager 生成NPC提议前，先生成心理旁白
narrative = narrator.generate(
    context=NarrativeContext.INNER_MONOLOGUE,
    location=current_location,
    emotion=response.get("emotion", "neutral"),
    chapter_info={"npc_name": "alice"}
)
```

### 6.2 输出数据结构

```python
@dataclass
class NarrativeOutput:
    text: str
    context: NarrativeContext
    duration_hint: str  # "short" | "medium" | "long"
    skip_allowed: bool  # 心理旁白默认可跳过
```

## 7. LLM 调用配置

```yaml
narrator:
  model: "minimax_m2_her"
  max_tokens: 300  # 心理描写较短，token限制更小
  temperature: 0.7  # 略低，保持叙事一致性
```

## 8. 实现要点

- INNER_MONOLOGUE 旁白**不**进入记忆系统
- skip_allowed 默认为 True，允许玩家跳过快速进入对话
- 长度控制在1-2句话，避免打断对话节奏
