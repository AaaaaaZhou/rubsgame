# OptionGenerator 开发指南

## 依赖关系

- **前置**: ClientManager
- **后续**: 被 GameLoopController 调用
- **配合**: StoryPlotManager（获取分支选项）、NarratorGenerator（行动旁白）

## 核心概念

选项生成两种时机：
- **时机C**：对话进行中每 3-5 轮穿插
- **时机D**：NPC 提出提议后

选项固定为 2 个候选 + 1 个空白自由输入。

## 文件: src/core/plot/option_generator.py

```python
"""
OptionGenerator - 选项生成器
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
import random

from .types import PlotState
from ...clients.manager import ClientManager
from ...utils.logger import get_logger

_logger = get_logger("rubsgame.option_generator")


class OptionType(Enum):
    """选项类型"""
    FIXED = "fixed"
    FREE_INPUT = "free_input"
    TRAVEL = "travel"


class OptionMode(Enum):
    """选项模式"""
    FORCE_CHOICE = "force_choice"   # 强制选择
    NORMAL = "normal"               # 普通选项
    TRAVEL = "travel"                # 移动选项


@dataclass
class DialogOption:
    """对话框选项"""
    type: OptionType = OptionType.FIXED
    content: str = ""
    action: Optional[str] = None
    target: Optional[str] = None


@dataclass
class OptionOutput:
    """选项输出"""
    options: List[DialogOption]
    mode: OptionMode = OptionMode.NORMAL
    expires_at: Optional[int] = None  # 超时回合数，None表示不超时


# NPC提议后的固定选项
NPC_SUGGESTION_OPTIONS = [
    DialogOption(type=OptionType.FIXED, content="接受", action="accept"),
    DialogOption(type=OptionType.FIXED, content="拒绝", action="reject"),
    DialogOption(type=OptionType.FREE_INPUT, content="（自由输入）", action=None),
]


class OptionGenerator:
    """选项生成器"""

    CONVERSATION_PROMPT_TEMPLATE = """[System]
当前场景：{location}
当前NPC：{npc_name}
NPC角色设定：{persona_system_prompt}

基于以上对话上下文，生成2个符合{NPC_name}角色性格的候选回复选项。
每个选项不超过20字，格式为角色可能会说的一句话。

选项应该是：
- 推进对话的问题
- 角色的反应/回应
- 符合角色性格的自然对话

不要生成：
- 玩家视角的选择
- 开放性提问

直接输出选项，每行一个，不要加编号。"""

    def __init__(
        self,
        client_manager: ClientManager,
        model_name: str = "minimax_m2_her",
        option_interval_min: int = 3,
        option_interval_max: int = 5
    ):
        self._client = client_manager.get_client(model_name)
        self._model = model_name
        self._interval_min = option_interval_min
        self._interval_max = option_interval_max
        self._next_option_turn: Optional[int] = None

    def reset_interval(self):
        """重置选项间隔计数"""
        self._next_option_turn = None

    def should_generate_option(
        self,
        conversation_turns: int,
        last_option_turn: int,
        npc_suggestion_pending: bool,
        is_branch_point: bool
    ) -> bool:
        """判断是否需要生成选项"""

        # 分支点不自动生成，等待玩家选择
        if is_branch_point:
            return False

        # NPC提议待确认，不生成新选项
        if npc_suggestion_pending:
            return False

        # 还没到间隔轮次
        interval = random.randint(self._interval_min, self._interval_max)
        if conversation_turns - last_option_turn < interval:
            return False

        return True

    def generate_in_conversation_options(
        self,
        chat_history: List[dict],
        npc_name: str,
        location: str,
        persona_system_prompt: str
    ) -> OptionOutput:
        """对话中穿插的选项生成"""

        prompt = self.CONVERSATION_PROMPT_TEMPLATE.format(
            location=location,
            npc_name=npc_name,
            persona_system_prompt=persona_system_prompt[:500]  # 截断避免token过多
        )

        # 构建消息，只取最近几轮
        recent_history = chat_history[-6:] if len(chat_history) > 6 else chat_history
        messages = [{"role": "system", "content": prompt}]
        for msg in recent_history:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

        response = self._client.chat(messages)
        lines = [line.strip() for line in response.strip().split("\n") if line.strip()]

        # 解析选项
        options = []
        for i, line in enumerate(lines[:2]):  # 最多2个
            options.append(DialogOption(
                type=OptionType.FIXED,
                content=line[:50],  # 限制长度
                action=f"option_{i+1}"
            ))

        # 添加空白选项
        options.append(DialogOption(
            type=OptionType.FREE_INPUT,
            content="（自由输入）",
            action=None
        ))

        _logger.debug(f"Generated {len(options)} in-conversation options")

        return OptionOutput(options=options, mode=OptionMode.NORMAL)

    def generate_npc_suggestion_options(
        self,
        suggestion_type: str = "invitation"
    ) -> OptionOutput:
        """NPC提议后的选项生成"""

        options = [
            DialogOption(type=OptionType.FIXED, content="接受", action="accept"),
            DialogOption(type=OptionType.FIXED, content="拒绝", action="reject"),
            DialogOption(type=OptionType.FREE_INPUT, content="（自由输入）", action=None),
        ]

        return OptionOutput(options=options, mode=OptionMode.FORCE_CHOICE)

    def generate_travel_options(
        self,
        available_locations: List[str],
        current_location: str
    ) -> OptionOutput:
        """地点移动选项生成"""

        options = []
        for loc in available_locations:
            if loc != current_location:  # 排除当前位置
                options.append(DialogOption(
                    type=OptionType.TRAVEL,
                    content=f"前往 {loc}",
                    action="travel",
                    target=loc
                ))

        # 如果没有可移动地点，返回空
        if not options:
            return OptionOutput(options=[], mode=OptionMode.NORMAL)

        return OptionOutput(options=options, mode=OptionMode.TRAVEL)

    def generate_branch_options(
        self,
        branches: List,  # List[Branch]
        include_free_input: bool = True
    ) -> OptionOutput:
        """分支选择选项生成"""

        options = []
        for branch in branches:
            options.append(DialogOption(
                type=OptionType.FIXED,
                content=branch.label,
                action="branch",
                target=branch.id
            ))

        if include_free_input:
            options.append(DialogOption(
                type=OptionType.FREE_INPUT,
                content="（自由输入）",
                action=None
            ))

        return OptionOutput(options=options, mode=OptionMode.FORCE_CHOICE)
```

## 与其他模块配合

### 与 StoryPlotManager 配合

```python
# GameLoopController 中
class GameLoopController:
    def _get_options(self, session, plot_state):
        choices = self._plot_manager.get_available_choices()

        if choices:
            # 分支点，生成强制选择
            return self._option_gen.generate_branch_options(choices)

        if self._option_gen.should_generate_option(
            session.turn_count,
            session.last_option_turn,
            session.npc_suggestion_pending is not None,
            plot_state.is_branch_point
        ):
            # 对话穿插
            persona = self._asset_manager.get_current_persona()
            return self._option_gen.generate_in_conversation_options(
                chat_history=session.full_history[-10:],
                npc_name=session.bound_npc_id,
                location=session.current_location,
                persona_system_prompt=persona.get_system_context() if persona else ""
            )

        return None
```

### 与 NarratorGenerator 配合

```python
# 玩家选择选项后，先生成行动旁白
class GameLoopController:
    def _on_option_selected(self, option: DialogOption, session):
        if option.type == OptionType.FIXED:
            narrative = self._narrator.generate(
                context=NarrativeContext.ACTION_RESULT,
                location=session.current_location,
                emotion=session.last_emotion,
                action_description=option.content
            )
            return {"narrative": narrative, "action": option.action}

        return {"action": option.action}
```

### 与 EngineCore 配合

```python
# EngineCore.chat() 返回后，检查是否有NPC提议
class GameLoopController:
    def on_llm_response(self, response, session):
        if response.get("suggestion"):
            options = self._option_gen.generate_npc_suggestion_options(
                response["suggestion"]["type"]
            )
            session.npc_suggestion_pending = response["suggestion"]
            return options

        return self._get_options(session, self._plot_manager.get_current_state())
```

## Session 扩展

```python
# ConversationSession 中新增字段
class ConversationSession:
    # ... 现有字段 ...

    last_option_turn: int = 0  # 上次生成选项时的对话轮次
    option_pending: Optional[DialogOption] = None  # 当前悬挂的选项
    npc_suggestion_pending: Optional[dict] = None  # NPC提议待确认
```

## 测试用例骨架

```python
# unittest/core/plot/test_option_generator.py
import pytest
from unittest.mock import Mock
from src.core.plot.option_generator import (
    OptionGenerator, DialogOption, OptionType, OptionMode
)
from src.core.plot.types import Branch


class TestOptionGenerator:
    @pytest.fixture
    def mock_client_manager(self):
        manager = Mock()
        client = Mock()
        client.chat.return_value = "你好吗？\n今天天气不错"
        manager.get_client.return_value = client
        return manager

    def test_should_generate_option(self, mock_client_manager):
        gen = OptionGenerator(mock_client_manager)

        # 间隔内，不生成
        assert not gen.should_generate_option(2, 0, False, False)

        # 超过间隔，生成
        assert gen.should_generate_option(5, 0, False, False)

        # 分支点，不生成
        assert not gen.should_generate_option(10, 0, False, True)

        # NPC提议待确认，不生成
        assert not gen.should_generate_option(10, 0, True, False)

    def test_generate_npc_suggestion_options(self, mock_client_manager):
        gen = OptionGenerator(mock_client_manager)
        output = gen.generate_npc_suggestion_options()

        assert len(output.options) == 3
        assert output.options[0].content == "接受"
        assert output.options[1].content == "拒绝"
        assert output.options[2].type == OptionType.FREE_INPUT
        assert output.mode == OptionMode.FORCE_CHOICE

    def test_generate_travel_options(self, mock_client_manager):
        gen = OptionGenerator(mock_client_manager)
        locations = ["咖啡馆", "图书馆", "公园"]
        output = gen.generate_travel_options(locations, "咖啡馆")

        assert len(output.options) == 2
        assert output.options[0].target == "图书馆"
        assert output.options[1].target == "公园"
```

## LLM 调用配置

在 `config/settings.yaml` 中增加：

```yaml
option_generator:
  model: "minimax_m2_her"
  max_tokens: 150
  temperature: 0.9
  interval_min: 3
  interval_max: 5
```
