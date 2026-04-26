# NarratorGenerator 模块设计

## 1. 职责

根据当前剧情状态生成四类旁白：
- **场景描述**：进入/离开场景时的环境描写
- **情绪/氛围渲染**：烘托当前情境
- **剧情过渡**：章节切换、时间跳跃
- **行动描述**：玩家空白选项执行后的结果描述

## 2. NarrativeContext 枚举

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
```

## 3. 旁白生成策略

### 3.1 触发条件

| Context | 触发时机 | 来源 |
|---------|---------|------|
| SCENE_ENTER | 玩家位置变化 | StoryPlotManager.move_to_location() |
| SCENE_EXIT | 离开某场景时 | OptionGenerator 选择"离开" |
| EMOTION_BUILD | 连续3轮同情绪后 | GameLoopController 计数 |
| TRANSITION | 章节切换时 | StoryPlotManager 章节切换 |
| ACTION_RESULT | 玩家空白选项执行后 | EngineCore.chat() 返回后 |
| CHAPTER_START | 新章节第一个节点 | StoryPlotManager.load_chapter() |
| CHAPTER_END | 章节最后一个节点完成后 | StoryPlotManager 节点遍历结束 |
| FREE_EXPLORE | 进入自由探索模式 | StoryPlotManager.is_exploring()=True |

### 3.2 风格控制

旁白风格需与当前情绪基调一致：

```python
EMOTION_STYLES = {
    "happy": "温馨轻快",
    "sad": "低沉忧郁",
    "tense": "紧张悬疑",
    "romantic": "浪漫柔和",
    "mysterious": "神秘诡异",
    "neutral": "平实自然"
}
```

## 4. 主要方法

```python
class NarratorGenerator:
    def __init__(self, client_manager: ClientManager):
        self._client = client_manager.get_client()

    def generate(
        self,
        context: NarrativeContext,
        location: Optional[str] = None,
        emotion: str = "neutral",
        emotion_intensity: float = 0.5,
        chapter_info: Optional[dict] = None,
        extra_context: Optional[str] = None
    ) -> str:
        """生成旁白文本"""
```

## 5. Prompt 模板

```
[System]
当前旁白类型：{narrative_context}
当前场景：{location}
当前情绪基调：{emotion}（{style}）
主线进度：{chapter_name} - {node_id}

请生成一段{narrative_context}类型的旁白，
长度为{length}句话，
风格与当前"{emotion}"情绪一致。
{freeze_length}时使用具体细节描写；{transition}时使用时间/空间跳跃句式。
```

## 6. 与其他模块的配合

### 6.1 与 StoryPlotManager 配合

```python
# StoryPlotManager 在状态变化时通知 NarratorGenerator
class StoryPlotManager:
    def __init__(self, narrator: NarratorGenerator):
        self._narrator = narrator

    def advance_to(self, node_id):
        node = self.get_node(node_id)
        if node.narration_type:
            # 触发对应类型的旁白
            self._narrator.generate(node.narration_type, ...)
```

### 6.2 与 EngineCore 配合

```python
# EngineCore.chat() 返回后，检查是否需要行动旁白
response = engine.chat(user_input, session_id)

if response.get("action_result"):
    # 玩家执行了空白选项，需要描述结果
    narrative = narrator.generate(
        context=NarrativeContext.ACTION_RESULT,
        location=session.current_location,
        emotion=response.get("emotion", "neutral"),
        emotion_intensity=response.get("intensity", 0.5)
    )
    response["narrative"] = narrative
```

### 6.3 与 OptionGenerator 配合

```python
# 玩家选择分支后，先生成行动旁白再展示选项
branch = option_generator.get_selected_branch()
narrative = narrator.generate(
    context=NarrativeContext.ACTION_RESULT,
    action_description=branch.label
)
```

### 6.4 与 GameLoopController 配合

```python
# GameLoopController 跟踪连续同情绪轮次
emotion_count = 0
last_emotion = None

def on_llm_response(response):
    global emotion_count, last_emotion
    if response.emotion == last_emotion:
        emotion_count += 1
    else:
        emotion_count = 1
        last_emotion = response.emotion

    if emotion_count >= 3:
        narrator.generate(NarrativeContext.EMOTION_BUILD, ...)
        emotion_count = 0  # 重置
```

## 7. 旁白渲染格式

输出给展示层时携带元数据：

```python
@dataclass
class NarrativeOutput:
    text: str
    context: NarrativeContext
    duration_hint: str  # "short" | "medium" | "long"
    skip_allowed: bool  # 某些旁白可跳过
```

## 8. 记忆系统隔离

**重要**：旁白内容不进入记忆系统。MemoryManager 仅处理对话内容。

```python
# GameLoopController 中
session.add_message("user", user_input)
session.add_message("assistant", llm_response["content"])
# 旁白不记录到 session.history
```

## 9. LLM 调用配置

```yaml
narrator:
  model: "minimax_m2_her"
  max_tokens: 200
  temperature: 0.8
  # 旁白需要快速生成，使用较小token限制
```
