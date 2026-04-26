# NarratorGenerator 开发指南

## 依赖关系

- **前置**: 无强依赖，需 ClientManager 获取 LLM 客户端
- **后续**: 被 GameLoopController 调用
- **配合**: StoryPlotManager（提供上下文）

## 核心概念

NarratorGenerator 根据 NarrativeContext 生成五类旁白：场景描述、情绪渲染、剧情过渡、行动描述、心理活动（INNER_MONOLOGUE）。

## 文件: src/core/plot/narrator.py

```python
"""
NarratorGenerator - 旁白生成器
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .types import NarrativeContext
from ...clients.manager import ClientManager
from ...utils.logger import get_logger

_logger = get_logger("rubsgame.narrator")

EMOTION_STYLES = {
    "happy": "温馨轻快",
    "sad": "低沉忧郁",
    "tense": "紧张悬疑",
    "romantic": "浪漫柔和",
    "mysterious": "神秘诡异",
    "neutral": "平实自然"
}

CONTEXT_LENGTHS = {
    NarrativeContext.SCENE_ENTER: "2-3",
    NarrativeContext.SCENE_EXIT: "1-2",
    NarrativeContext.EMOTION_BUILD: "1",
    NarrativeContext.TRANSITION: "1-2",
    NarrativeContext.ACTION_RESULT: "2-3",
    NarrativeContext.CHAPTER_START: "2-3",
    NarrativeContext.CHAPTER_END: "1-2",
    NarrativeContext.FREE_EXPLORE: "1-2",
    NarrativeContext.INNER_MONOLOGUE: "1-2"
}


@dataclass
class NarrativeOutput:
    """旁白输出"""
    text: str
    context: NarrativeContext
    duration_hint: str  # "short" | "medium" | "long"
    skip_allowed: bool = True


class NarratorGenerator:
    """根据剧情状态生成旁白"""

    PROMPT_TEMPLATE = """[System]
当前旁白类型：{narrative_context}
当前场景：{location}
当前情绪基调：{emotion}（{style}）
主线进度：{chapter_name} - {node_id}

请生成一段{narrative_context}类型的旁白，
长度为{length}句话，
风格与当前"{emotion}"情绪一致。

要求：
- {requirements}
- 不要使用括号或特殊标记
- 直接输出旁白文本
"""

    def __init__(self, client_manager: ClientManager, model_name: str = "minimax_m2_her"):
        self._client = client_manager.get_client(model_name)
        self._model = model_name

    def generate(
        self,
        context: NarrativeContext,
        location: Optional[str] = None,
        emotion: str = "neutral",
        emotion_intensity: float = 0.5,
        chapter_name: str = "",
        node_id: str = "",
        action_description: Optional[str] = None,
        npc_name: Optional[str] = None,
        extra_context: Optional[str] = None
    ) -> NarrativeOutput:
        """生成旁白"""

        style = EMOTION_STYLES.get(emotion, "平实自然")
        length = CONTEXT_LENGTHS.get(context, "2")

        requirements = self._get_context_requirements(context, action_description, npc_name)

        prompt = self.PROMPT_TEMPLATE.format(
            narrative_context=self._get_context_name(context),
            location=location or "未知地点",
            emotion=emotion,
            style=style,
            chapter_name=chapter_name or "未知章节",
            node_id=node_id or "未知节点",
            length=length,
            requirements=requirements
        )

        if extra_context:
            prompt += f"\n\n额外上下文：{extra_context}"

        messages = [{"role": "user", "content": prompt}]
        response = self._client.chat(messages)

        text = response.strip()
        duration_hint = self._estimate_duration(context)

        _logger.debug(f"Generated narrative: context={context.value}, length={len(text)}")

        return NarrativeOutput(
            text=text,
            context=context,
            duration_hint=duration_hint,
            skip_allowed=context not in [NarrativeContext.CHAPTER_START]
        )

    def _get_context_name(self, context: NarrativeContext) -> str:
        names = {
            NarrativeContext.SCENE_ENTER: "场景描述",
            NarrativeContext.SCENE_EXIT: "场景离开",
            NarrativeContext.EMOTION_BUILD: "情绪铺垫",
            NarrativeContext.TRANSITION: "剧情过渡",
            NarrativeContext.ACTION_RESULT: "行动结果描述",
            NarrativeContext.CHAPTER_START: "章节开始",
            NarrativeContext.CHAPTER_END: "章节结束",
            NarrativeContext.FREE_EXPLORE: "自由探索",
            NarrativeContext.INNER_MONOLOGUE: "心理活动描写"
        }
        return names.get(context, "场景描述")

    def _get_context_requirements(self, context: NarrativeContext, action_desc: Optional[str], npc_name: Optional[str] = None) -> str:
        requirements = {
            NarrativeContext.SCENE_ENTER: "描写新场景的环境细节，营造氛围",
            NarrativeContext.SCENE_EXIT: "描述离开的场景，留下悬念",
            NarrativeContext.EMOTION_BUILD: "烘托情绪，不要有剧情推进",
            NarrativeContext.TRANSITION: "使用时间/空间跳跃句式，自然过渡",
            NarrativeContext.ACTION_RESULT: f"描述玩家执行「{action_desc or='行动'}」后的结果",
            NarrativeContext.CHAPTER_START: "描写新章节的开场，给玩家期待感",
            NarrativeContext.CHAPTER_END: "留下悬念或情感余韵",
            NarrativeContext.FREE_EXPLORE: "简洁描述当前状态，给玩家方向感",
            NarrativeContext.INNER_MONOLOGUE: f"从NPC {npc_name or='某角色'} 视角描写其内心状态，使用模糊/非确定性措辞（如"似乎"、"也许"、"隐约感到"），减少使用确定性措辞"
        }
        return requirements.get(context, "")

    def _estimate_duration(self, context: NarrativeContext) -> str:
        durations = {
            NarrativeContext.SCENE_ENTER: "medium",
            NarrativeContext.SCENE_EXIT: "short",
            NarrativeContext.EMOTION_BUILD: "short",
            NarrativeContext.TRANSITION: "short",
            NarrativeContext.ACTION_RESULT: "medium",
            NarrativeContext.CHAPTER_START: "long",
            NarrativeContext.CHAPTER_END: "short",
            NarrativeContext.FREE_EXPLORE: "short",
            NarrativeContext.INNER_MONOLOGUE: "short"
        }
        return durations.get(context, "short")
```

## 与其他模块配合

### 与 StoryPlotManager 配合

```python
# GameLoopController 中
from .narrator import NarratorGenerator
from .types import NarrativeContext

class GameLoopController:
    def __init__(self, plot_manager: StoryPlotManager, narrator: NarratorGenerator, ...):
        self._plot = plot_manager
        self._narrator = narrator

    def _generate_node_narrative(self, session):
        state = self._plot.get_current_state()
        node = self._plot.get_current_node()

        if node and node.narration_type:
            narrative = self._narrator.generate(
                context=node.narration_type,
                location=session.current_location,
                emotion=session.last_emotion,
                chapter_name=state.chapter_id,
                node_id=state.node_id
            )
            return narrative
        return None
```

### 与 EngineCore 配合

```python
# EngineCore.chat() 返回后，检查是否需要行动旁白
class GameLoopController:
    def on_llm_response(self, response, session):
        if response.get("action_taken"):
            narrative = self._narrator.generate(
                context=NarrativeContext.ACTION_RESULT,
                location=session.current_location,
                emotion=response.get("emotion", "neutral"),
                action_description=response.get("action_taken")
            )
            response["narrative"] = narrative
        return response
```

## 情绪追踪逻辑

GameLoopController 需跟踪连续同情绪轮次：

```python
class EmotionTracker:
    def __init__(self, threshold: int = 3):
        self._count = 0
        self._last_emotion = None
        self._threshold = threshold

    def record(self, emotion: str) -> bool:
        """记录情绪，返回是否达到铺垫阈值"""
        if emotion == self._last_emotion:
            self._count += 1
        else:
            self._count = 1
            self._last_emotion = emotion

        return self._count >= self._threshold

    def reset(self):
        self._count = 0
        self._last_emotion = None
```

## 测试用例骨架

```python
# unittest/core/plot/test_narrator.py
import pytest
from unittest.mock import Mock, MagicMock
from src.core.plot.narrator import NarratorGenerator, NarrativeOutput
from src.core.plot.types import NarrativeContext


class TestNarratorGenerator:
    @pytest.fixture
    def mock_client_manager(self):
        manager = Mock()
        client = Mock()
        client.chat.return_value = "你走进咖啡馆，阳光透过窗户洒进来。"
        manager.get_client.return_value = client
        return manager

    def test_generate_scene_enter(self, mock_client_manager):
        narrator = NarratorGenerator(mock_client_manager)
        result = narrator.generate(
            context=NarrativeContext.SCENE_ENTER,
            location="咖啡馆",
            emotion="neutral"
        )
        assert isinstance(result, NarrativeOutput)
        assert result.context == NarrativeContext.SCENE_ENTER
        assert len(result.text) > 0

    def test_estimate_duration(self, mock_client_manager):
        narrator = NarratorGenerator(mock_client_manager)
        assert narrator._estimate_duration(NarrativeContext.CHAPTER_START) == "long"
        assert narrator._estimate_duration(NarrativeContext.EMOTION_BUILD) == "short"
```

## LLM 调用配置

在 `config/settings.yaml` 中增加：

```yaml
narrator:
  model: "minimax_m2_her"
  max_tokens: 300
  temperature: 0.7
```
