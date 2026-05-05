"""
旁白生成器
根据 NarrativeContext 生成场景/氛围/过渡/行动描述
"""
import logging
from typing import Optional

from .types import NarrativeOutput, NarrativeType
from ...clients.manager import ClientManager
from ...utils.logger import get_logger

_logger = get_logger("rubsgame.narrator")


class NarratorGenerator:
    """旁白生成器 - 调用 LLM 生成叙事文本"""

    EMOTION_STYLES = {
        "happy": "温馨轻快，带有阳光般的暖意",
        "sad": "低沉忧郁，如细雨绵绵",
        "tense": "紧张悬疑，节奏急促",
        "romantic": "浪漫柔和，如微风轻拂",
        "mysterious": "神秘诡异，暗藏玄机",
        "neutral": "平实自然，如日常流水"
    }

    CONTEXT_LENGTHS = {
        NarrativeType.SCENE_ENTER: "2-3",
        NarrativeType.SCENE_EXIT: "1-2",
        NarrativeType.EMOTION_BUILD: "1",
        NarrativeType.TRANSITION: "2",
        NarrativeType.ACTION_RESULT: "2-3",
        NarrativeType.CHAPTER_START: "3-4",
        NarrativeType.CHAPTER_END: "2-3",
        NarrativeType.FREE_EXPLORE: "2",
        NarrativeType.INNER_MONOLOGUE: "2-3",
    }

    DURATION_HINTS = {
        NarrativeType.SCENE_ENTER: "medium",
        NarrativeType.SCENE_EXIT: "short",
        NarrativeType.EMOTION_BUILD: "short",
        NarrativeType.TRANSITION: "medium",
        NarrativeType.ACTION_RESULT: "medium",
        NarrativeType.CHAPTER_START: "long",
        NarrativeType.CHAPTER_END: "medium",
        NarrativeType.FREE_EXPLORE: "short",
        NarrativeType.INNER_MONOLOGUE: "medium",
    }

    def __init__(
        self,
        client_manager: ClientManager,
        model_name: str = "minimax_m2_her"
    ):
        """初始化

        Args:
            client_manager: LLM 客户端管理器
            model_name: 使用的模型名称
        """
        self._client_mgr = client_manager
        self._model_name = model_name

    def generate(
        self,
        context: NarrativeType,
        location: Optional[str] = None,
        emotion: str = "neutral",
        emotion_intensity: float = 0.5,
        chapter_name: Optional[str] = None,
        node_id: Optional[str] = None,
        action_description: Optional[str] = None,
        npc_name: Optional[str] = None,
        extra_context: Optional[str] = None
    ) -> NarrativeOutput:
        """生成旁白文本

        Args:
            context: 旁白类型
            location: 当前场景地点
            emotion: 当前情绪基调
            emotion_intensity: 情绪强度 0-1
            chapter_name: 当前章节名
            node_id: 当前节点ID
            action_description: 玩家行动描述（用于ACTION_RESULT）
            npc_name: 涉及的NPC名称
            extra_context: 额外上下文

        Returns:
            NarrativeOutput 对象
        """
        style = self.EMOTION_STYLES.get(emotion, self.EMOTION_STYLES["neutral"])
        length = self.CONTEXT_LENGTHS.get(context, "2-3")
        duration = self.DURATION_HINTS.get(context, "medium")

        # 构建 Prompt
        prompt = self._build_prompt(
            context=context,
            location=location,
            emotion=emotion,
            style=style,
            chapter_name=chapter_name,
            node_id=node_id,
            length=length,
            action_description=action_description,
            npc_name=npc_name,
            extra_context=extra_context
        )

        # 调用 LLM
        try:
            client = self._client_mgr.get_client(self._model_name)
            messages = [{"role": "user", "content": prompt}]
            response = client.chat(messages, temperature=0.7, max_tokens=300)
            text = response.strip() if response else ""
        except Exception as e:
            _logger.warning(f"Narrator LLM call failed: {e}, using fallback")
            text = self._fallback_text(context, location, emotion)

        skip_allowed = context in (
            NarrativeType.EMOTION_BUILD,
            NarrativeType.FREE_EXPLORE,
            NarrativeType.ACTION_RESULT
        )

        return NarrativeOutput(
            text=text,
            context=context,
            duration_hint=duration,
            skip_allowed=skip_allowed
        )

    def _build_prompt(
        self,
        context: NarrativeType,
        location: Optional[str],
        emotion: str,
        style: str,
        chapter_name: Optional[str],
        node_id: Optional[str],
        length: str,
        action_description: Optional[str],
        npc_name: Optional[str],
        extra_context: Optional[str]
    ) -> str:
        """构建 Prompt"""
        context_name = self._get_context_name(context)
        requirements = self._get_context_requirements(context, action_description, npc_name)

        location_str = f"当前场景：{location}" if location else "当前场景：未知"
        chapter_str = f"主线进度：{chapter_name} - {node_id}" if chapter_name and node_id else ""

        prompt = f"""[System]
当前旁白类型：{context_name}
{location_str}
当前情绪基调：{emotion}（{style}）
{chapter_str}

请生成一段{context_name}类型的旁白。
{requirements}
风格与当前"{emotion}"情绪一致，长度约{length}句话。

请直接输出旁白文本，不要加引号或任何标记。"""

        if extra_context:
            prompt += f"\n\n额外信息：{extra_context}"

        return prompt

    def _get_context_name(self, context: NarrativeType) -> str:
        """获取旁白类型的中文名称"""
        names = {
            NarrativeType.SCENE_ENTER: "场景进入",
            NarrativeType.SCENE_EXIT: "场景离开",
            NarrativeType.EMOTION_BUILD: "情绪铺垫",
            NarrativeType.TRANSITION: "剧情过渡",
            NarrativeType.ACTION_RESULT: "行动结果",
            NarrativeType.CHAPTER_START: "章节开始",
            NarrativeType.CHAPTER_END: "章节结束",
            NarrativeType.FREE_EXPLORE: "自由探索",
            NarrativeType.INNER_MONOLOGUE: "内心独白",
        }
        return names.get(context, "旁白")

    def _get_context_requirements(
        self,
        context: NarrativeType,
        action_description: Optional[str],
        npc_name: Optional[str]
    ) -> str:
        """获取不同旁白类型的要求"""
        if context == NarrativeType.SCENE_ENTER:
            req = "描写新场景的环境、氛围和细节，让读者身临其境。"
        elif context == NarrativeType.SCENE_EXIT:
            req = "描写离开场景时的心情和场景的收尾印象。"
        elif context == NarrativeType.EMOTION_BUILD:
            req = "渲染情绪氛围，为接下来的剧情做铺垫。"
        elif context == NarrativeType.TRANSITION:
            req = "使用时间或空间跳跃的句式，简短有力地过渡。"
        elif context == NarrativeType.ACTION_RESULT:
            if action_description:
                req = f"描述玩家「{action_description}」的结果，使用第三人称旁白视角。"
            else:
                req = "描述玩家行动的结果，使用第三人称旁白视角。"
        elif context == NarrativeType.CHAPTER_START:
            req = "建立新章节的氛围，介绍时间地点和人物状态。"
        elif context == NarrativeType.CHAPTER_END:
            req = "收束本章情节，留有余韵，可以有承前启后的句子。"
        elif context == NarrativeType.FREE_EXPLORE:
            req = "描写当前自由探索状态的感受和周围环境。"
        elif context == NarrativeType.INNER_MONOLOGUE:
            if npc_name:
                req = f"以{npc_name}的视角描写内心独白，真诚而细腻。"
            else:
                req = "描写角色内心独白，真诚而细腻。"
        else:
            req = "用简洁的文字描写场景。"

        return req

    def _estimate_duration(self, context: NarrativeType) -> str:
        """估算旁白时长级别"""
        return self.DURATION_HINTS.get(context, "medium")

    def _fallback_text(
        self,
        context: NarrativeType,
        location: Optional[str],
        emotion: str
    ) -> str:
        """LLM 不可用时的回退文本"""
        location_str = location or "某处"
        emotion_words = {
            "happy": "阳光明媚",
            "sad": "阴雨绵绵",
            "tense": "气氛紧张",
            "romantic": "微风轻拂",
            "mysterious": "迷雾重重",
            "neutral": "一切如常"
        }
        word = emotion_words.get(emotion, "一切如常")

        fallbacks = {
            NarrativeType.SCENE_ENTER: f"阳光洒在{location_str}，{word}。",
            NarrativeType.SCENE_EXIT: f"离开了{location_str}，心中带着几分不舍。",
            NarrativeType.EMOTION_BUILD: "空气中弥漫着微妙的氛围……",
            NarrativeType.TRANSITION: "时光流转，下一段故事即将展开。",
            NarrativeType.ACTION_RESULT: "行动的结果逐渐显现。",
            NarrativeType.CHAPTER_START: f"故事在{location_str}继续展开。",
            NarrativeType.CHAPTER_END: "这一章的故事暂时落幕。",
            NarrativeType.FREE_EXPLORE: f"在{location_str}中自由探索着。",
            NarrativeType.INNER_MONOLOGUE: "心中思绪万千……",
        }
        return fallbacks.get(context, "旁白继续。")