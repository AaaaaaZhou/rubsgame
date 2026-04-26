# OptionGenerator 模块设计

## 1. 职责

在两种时机生成玩家选项：
- **时机C**：对话进行中随机穿插，每3-5轮生成选项
- **时机D**：NPC 提出邀请/建议后，生成 [接受/拒绝/自由输入] 选项

选项固定为 2 个候选 + 1 个空白自由输入。

## 2. DialogOption 数据结构

```python
@dataclass
class DialogOption:
    type: OptionType           # 选项类型
    content: str              # 显示文字
    action: Optional[str]     # 执行动作标识
    target: Optional[str]     # 动作目标（如地点名称）

class OptionType(Enum):
    FIXED        # 固定选项，content为显示文字
    FREE_INPUT   # 空白选项，等待玩家自由输入
    TRAVEL       # 移动选项，target为地点
```

### 固定选项模板

```python
# NPC提议后的选项
NPC_SUGGESTION_OPTIONS = [
    DialogOption(type=FIXED, content="接受", action="accept"),
    DialogOption(type=FIXED, content="拒绝", action="reject"),
    DialogOption(type=FREE_INPUT, content="（自由输入）", action=None),
]

# 移动选项
LOCATION_OPTIONS = [
    DialogOption(type=TRAVEL, content="前往 {location_name}", action="travel", target="{location}"),
]
```

## 3. 主要方法

```python
class OptionGenerator:
    def __init__(self, client_manager: ClientManager):
        self._client = client_manager.get_client()

    def should_generate_option(
        self,
        conversation_turns: int,
        last_option_turn: int,
        npc_suggestion_pending: bool
    ) -> bool:
        """判断是否需要生成选项"""

    def generate_in_conversation_options(
        self,
        chat_history: List[Message],
        npc_name: str,
        plot_context: Optional[dict] = None
    ) -> List[DialogOption]:
        """对话中穿插的选项生成"""

    def generate_npc_suggestion_options(
        self,
        suggestion_type: str  # "invitation" | "proposal" | "question"
    ) -> List[DialogOption]:
        """NPC提议后的选项生成"""

    def generate_travel_options(
        self,
        available_locations: List[str]
    ) -> List[DialogOption]:
        """地点移动选项生成"""
```

## 4. 生成策略

### 4.1 时机C — 对话穿插选项

触发条件：
- `conversation_turns - last_option_turn >= random(3, 5)`
- 且当前不在分支选择节点
- 且不在 NPC 提议待确认状态

生成 Prompt：
```
[System]
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
```

### 4.2 时机D — NPC提议选项

当 EngineCore 返回的响应包含 `suggestion` 字段时触发：

```python
# NPC提议的响应格式
{
    "content": "要不我们明天一起去图书馆吧？",
    "suggestion": {
        "type": "invitation",  # or "proposal" | "question"
        "action_hint": "go_to_library_together"
    }
}
```

生成选项：`[接受] [拒绝] [（自由输入）]`

### 4.3 空白选项

空白选项内容固定为 `（自由输入）`，玩家选择后切换到自由对话输入模式。

## 5. 与其他模块的配合

### 5.1 与 StoryPlotManager 配合

```python
# OptionGenerator 从 StoryPlotManager 获取上下文
if plot_manager.is_exploring():
    # 自由探索模式，提供地点移动选项
    locations = plot_manager.get_available_locations()
    options = option_generator.generate_travel_options(locations)
elif plot_manager.is_branch_point():
    # 分支点，从章节配置获取分支
    branches = plot_manager.get_available_choices()
    options = [branch_to_option(b) for b in branches]
    options.append(DialogOption(type=FREE_INPUT, content="（自由输入）"))
```

### 5.2 与 EngineCore 配合

```python
# EngineCore.chat() 返回后，OptionGenerator 判断是否需要生成选项
class GameLoopController:
    def on_llm_response(self, response):
        if response.get("suggestion"):
            # NPC提议，生成接受/拒绝/自由输入
            options = option_generator.generate_npc_suggestion_options(
                response["suggestion"]["type"]
            )
        elif should_generate_option(...):
            # 对话穿插
            options = option_generator.generate_in_conversation_options(...)
        else:
            options = None

        return options
```

### 5.3 与 NarratorGenerator 配合

```python
# 选项展示前，先判断是否需要行动旁白
if selected_option.type == OptionType.FIXED:
    narrative = narrator.generate(
        NarrativeContext.ACTION_RESULT,
        action_description=selected_option.content
    )
    # 旁白在选项之前或之后由配置决定
    output = {"narrative": narrative, "options": [selected_option]}
```

## 6. 输出格式

```python
@dataclass
class OptionOutput:
    options: List[DialogOption]
    option_mode: OptionMode  # "force_choice" | "normal" | "travel"
    expires_at: Optional[int]  # 超时时间（回合数），None表示不超时

class OptionMode(Enum):
    FORCE_CHOICE   # 强制选择，不选不能继续
    NORMAL          # 普通选项，可以忽略继续对话
    TRAVEL          # 移动选项
```

## 7. Session 持久化

```python
# ConversationSession 中新增
class ConversationSession:
    last_option_turn: int      # 上次生成选项时的对话轮次
    option_pending: DialogOption  # 当前悬挂的选项（force_choice模式）
    npc_suggestion_pending: Optional[NpcSuggestion]  # NPC提议待确认
```

## 8. LLM 调用配置

```yaml
option_generator:
  model: "minimax_m2_her"
  max_tokens: 300
  temperature: 0.9
  # 选项生成需要一定随机性，temperature稍高
```

## 9. 选项展示规则

展示层（PowerShellInterface）根据 `option_mode` 决定展示方式：

- `FORCE_CHOICE`：选项以数字列表展示，玩家必须选择才能继续
- `NORMAL`：选项以斜体/灰色展示，玩家可选择也可直接输入
- `TRAVEL`：选项展示为"前往 [地点]"格式
