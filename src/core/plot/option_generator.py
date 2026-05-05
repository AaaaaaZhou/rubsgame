"""
选项生成器
在对话中穿插选项、NPC提议后选项、分支选项
"""
import random
import logging
from typing import List, Optional

from .types import (
    OptionOutput, OptionMode, DialogOption, OptionType
)
from ...clients.manager import ClientManager
from ...utils.logger import get_logger

_logger = get_logger("rubsgame.option_gen")


class OptionGenerator:
    """选项生成器"""

    NPC_SUGGESTION_OPTIONS = [
        DialogOption(type=OptionType.FIXED, content="好的，没问题", action="accept"),
        DialogOption(type=OptionType.FIXED, content="不了，谢谢", action="reject"),
        DialogOption(type=OptionType.FREE_INPUT, content="（自由输入）", action="free_input"),
    ]

    TRAVEL_OPTIONS = [
        DialogOption(type=OptionType.TRAVEL, content="老街", action="move", target="老街"),
        DialogOption(type=OptionType.TRAVEL, content="清溪河", action="move", target="清溪河"),
        DialogOption(type=OptionType.TRAVEL, content="咖啡店", action="move", target="咖啡店"),
    ]

    CONVERSATION_PROMPT = """[System]
当前对话上下文：
{chat_history}

当前场景：{location}
当前NPC：{npc_name}
NPC人设：{persona_system_prompt}

请根据对话上下文，生成3-5个玩家可能的回复选项。
选项应该符合角色特点，自然多样。

要求：
1. 选项长度为5-15个字
2. 包含至少1个开放式选项（如询问、表达感受等）
3. 选项之间要有差异化
4. 用 | 分隔每个选项

格式：选项1 | 选项2 | 选项3"""

    def __init__(
        self,
        client_manager: ClientManager,
        model_name: str = "minimax_m2_her",
        option_interval_min: int = 3,
        option_interval_max: int = 5
    ):
        """初始化

        Args:
            client_manager: LLM 客户端管理器
            model_name: 使用的模型名称
            option_interval_min: 选项生成最小间隔（轮次）
            option_interval_max: 选项生成最大间隔（轮次）
        """
        self._client_mgr = client_manager
        self._model_name = model_name
        self._option_interval_min = option_interval_min
        self._option_interval_max = option_interval_max
        self._next_option_turn: Optional[int] = None

    def reset_interval(self) -> None:
        """重置选项生成间隔计数"""
        self._next_option_turn = None

    def should_generate_option(
        self,
        conversation_turns: int,
        last_option_turn: int,
        npc_suggestion_pending: bool = False,
        is_branch_point: bool = False
    ) -> bool:
        """判断是否应该生成选项

        Args:
            conversation_turns: 当前对话轮次
            last_option_turn: 上次生成选项时的轮次
            npc_suggestion_pending: 是否有NPC建议待处理
            is_branch_point: 是否为分支点

        Returns:
            是否应该生成选项
        """
        # 分支点强制等待选择，不生成选项
        if is_branch_point:
            return False

        # NPC建议待处理时，不生成额外选项
        if npc_suggestion_pending:
            return False

        # 首次检查，设置下次触发点
        if self._next_option_turn is None:
            self._next_option_turn = conversation_turns + random.randint(
                self._option_interval_min,
                self._option_interval_max
            )

        return conversation_turns >= self._next_option_turn

    def generate_in_conversation_options(
        self,
        chat_history: List[dict],
        npc_name: str,
        location: str,
        persona_system_prompt: str = ""
    ) -> OptionOutput:
        """在对话中生成穿插选项

        Args:
            chat_history: 对话历史
            npc_name: NPC名称
            location: 当前地点
            persona_system_prompt: NPC人设描述

        Returns:
            OptionOutput 对象
        """
        # 构建历史摘要
        history_text = self._format_chat_history(chat_history)

        prompt = self.CONVERSATION_PROMPT.format(
            chat_history=history_text,
            location=location,
            npc_name=npc_name,
            persona_system_prompt=persona_system_prompt or "普通中学生"
        )

        try:
            client = self._client_mgr.get_client(self._model_name)
            messages = [{"role": "user", "content": prompt}]
            response = client.chat(messages, temperature=0.9, max_tokens=150)
            options = self._parse_options_response(response)
        except Exception as e:
            _logger.warning(f"Option generation LLM failed: {e}")
            options = []

        if not options:
            options = self._default_conversation_options()

        return OptionOutput(options=options, mode=OptionMode.NORMAL)

    def generate_npc_suggestion_options(self, suggestion_type: str = "default") -> OptionOutput:
        """生成NPC提议后的选项（接受/拒绝/自由输入）

        Returns:
            OptionOutput with accept/reject/free options
        """
        return OptionOutput(
            options=self.NPC_SUGGESTION_OPTIONS.copy(),
            mode=OptionMode.FORCE_CHOICE
        )

    def generate_travel_options(
        self,
        available_locations: List[str],
        current_location: Optional[str] = None
    ) -> OptionOutput:
        """生成旅行/移动选项

        Args:
            available_locations: 可前往的地点列表
            current_location: 当前位置（排除）

        Returns:
            OptionOutput with TRAVEL type options
        """
        options = []
        for loc in available_locations:
            if loc != current_location:
                options.append(DialogOption(
                    type=OptionType.TRAVEL,
                    content=loc,
                    action="move",
                    target=loc
                ))

        if not options:
            options = self._default_travel_options()

        return OptionOutput(options=options, mode=OptionMode.TRAVEL)

    def generate_branch_options(
        self,
        branches: List,
        include_free_input: bool = True
    ) -> OptionOutput:
        """生成分支选项

        Args:
            branches: 分支列表
            include_free_input: 是否包含自由输入选项

        Returns:
            OptionOutput with branch options
        """
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
                action="free_input"
            ))

        return OptionOutput(options=options, mode=OptionMode.FORCE_CHOICE)

    def _format_chat_history(self, chat_history: List[dict]) -> str:
        """格式化对话历史为文本"""
        if not chat_history:
            return "(无历史对话)"

        lines = []
        for msg in chat_history[-10:]:  # 最近10条
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                lines.append(f"玩家：{content}")
            elif role == "assistant":
                lines.append(f"NPC：{content}")

        return "\n".join(lines) if lines else "(无历史对话)"

    def _parse_options_response(self, response: str) -> List[DialogOption]:
        """解析 LLM 返回的选项"""
        if not response:
            return []

        options = []
        parts = response.split("|")
        for part in parts:
            label = part.strip()
            if label:
                options.append(DialogOption(
                    type=OptionType.FIXED,
                    content=label,
                    action="chat"
                ))

        return options

    def _default_conversation_options(self) -> List[DialogOption]:
        """默认对话选项（LLM不可用时）"""
        return [
            DialogOption(type=OptionType.FIXED, content="你最近怎么样？", action="chat"),
            DialogOption(type=OptionType.FIXED, content="有什么新鲜事吗？", action="chat"),
            DialogOption(type=OptionType.FIXED, content="你想聊些什么？", action="chat"),
        ]

    def _default_travel_options(self) -> List[DialogOption]:
        """默认旅行选项"""
        return [
            DialogOption(type=OptionType.TRAVEL, content="老街", action="move", target="老街"),
            DialogOption(type=OptionType.TRAVEL, content="清溪河", action="move", target="清溪河"),
        ]