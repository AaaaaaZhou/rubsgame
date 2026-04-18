"""
PowerShell 交互界面模块
提供 REPL 对话循环和指令解析
"""
import sys
import logging
from typing import Optional, Tuple

from ..core.engine import EngineCore
from ..utils.logger import get_logger

_logger = get_logger("rubsgame.interface")


class PowerShellInterface:
    """PowerShell 交互界面"""

    COMMANDS = {
        "/save": "保存当前会话",
        "/load": "加载会话 (用法: /load <session_id>)",
        "/role": "切换人设 (用法: /role <persona_name>)",
        "/world": "加载世界观 (用法: /world <world_name>)",
        "/emotion": "情绪开关 (用法: /emotion toggle|show)",
        "/status": "显示状态",
        "/sessions": "列出所有会话",
        "/exit": "退出 (自动保存)",
        "/help": "显示帮助",
    }

    def __init__(self, engine: EngineCore):
        self._engine = engine
        self._current_session_id = "default"
        self._emotion_enabled = True
        self._logger = _logger

    def run_repl(self) -> None:
        """主 REPL 循环"""
        self._print_welcome()

        while True:
            try:
                user_input = input("\n> ").strip()
                if not user_input:
                    continue

                # 指令解析
                if user_input.startswith("/"):
                    cmd, args = self._parse_command(user_input)
                    if cmd == "/exit":
                        self._do_exit()
                        break
                    elif cmd == "/help":
                        self._print_help()
                    elif cmd == "/status":
                        self._print_status()
                    elif cmd == "/sessions":
                        self._print_sessions()
                    elif cmd == "/save":
                        self._do_save()
                    elif cmd == "/load":
                        self._do_load(args)
                    elif cmd == "/role":
                        self._do_role(args)
                    elif cmd == "/world":
                        self._do_world(args)
                    elif cmd == "/emotion":
                        self._do_emotion(args)
                    else:
                        print(f"未知指令: {cmd}，输入 /help 查看帮助")
                else:
                    # 对话
                    self._do_chat(user_input)

            except KeyboardInterrupt:
                self._do_exit()
                break
            except Exception as e:
                print(f"[Error] {e}")

    def _parse_command(self, line: str) -> Tuple[str, list]:
        parts = line.split(maxsplit=1)
        cmd = parts[0]
        args = parts[1].split() if len(parts) > 1 else []
        return cmd, args

    # ==================== Command Handlers ====================

    def _do_chat(self, user_input: str) -> None:
        """处理对话"""
        result = self._engine.chat(user_input, self._current_session_id)
        self._render_output(result)

    def _do_exit(self) -> None:
        """退出"""
        self._engine.finalize_and_save(self._current_session_id)
        print("\n会话已保存 goodbye!")

    def _do_save(self) -> None:
        self._engine.save_session(self._current_session_id)
        print(f"会话 '{self._current_session_id}' 已保存")

    def _do_load(self, args: list) -> None:
        if not args:
            print("用法: /load <session_id>")
            return
        session_id = args[0]
        try:
            self._engine.get_or_create_session(session_id)
            self._current_session_id = session_id
            print(f"已切换到会话: {session_id}")
        except FileNotFoundError:
            print(f"会话 '{session_id}' 不存在")

    def _do_role(self, args: list) -> None:
        if not args:
            print("用法: /role <persona_name>")
            return
        try:
            self._engine.load_persona(args[0])
            print(f"已加载人设: {args[0]}")
        except FileNotFoundError as e:
            print(f"人设加载失败: {e}")

    def _do_world(self, args: list) -> None:
        if not args:
            print("用法: /world <world_name>")
            return
        try:
            self._engine.load_world(args[0])
            print(f"已加载世界观: {args[0]}")
        except FileNotFoundError as e:
            print(f"世界观加载失败: {e}")

    def _do_emotion(self, args: list) -> None:
        if not args or args[0] == "toggle":
            self._emotion_enabled = not self._emotion_enabled
            print(f"情绪渲染: {'开启' if self._emotion_enabled else '关闭'}")
        elif args[0] == "show":
            print(f"情绪渲染: {'开启' if self._emotion_enabled else '关闭'}")

    def _print_status(self) -> None:
        status = self._engine.get_status(self._current_session_id)
        if "error" in status:
            print(status["error"])
            return
        print(f"""
╭─ Session Status ────────────────╮
│ Session: {status['session_id']}
│ Persona: {status['persona'] or '(none)'}
│ World:   {status['world'] or '(none)'}
│ History: {status['history_count']} messages
│ Memory:  {status['memory_count']} items
│ Tokens:  ~{status['token_estimate']}
╰──────────────────────────────────╯""")

    def _print_sessions(self) -> None:
        sessions = self._engine.list_sessions()
        if sessions:
            print("可用会话:", ", ".join(sessions))
        else:
            print("暂无会话")

    def _render_output(self, result: dict) -> None:
        """渲染输出"""
        content = result["content"]
        emotion = result.get("emotion", "neutral")
        intensity = result.get("intensity", 0.5)

        print(f"\n[AI] {content}")

        if self._emotion_enabled:
            # TODO: Phase 4 接入素材渲染引擎
            emotion_symbol = self._emotion_symbol(emotion, intensity)
            print(f"       {emotion_symbol}")

    def _emotion_symbol(self, emotion: str, intensity: float) -> str:
        """简单的情绪符号映射（后续由素材引擎替换）"""
        symbols = {
            "happy": ["(^_^)", "(◕‿◕)", "ヽ(✿ﾟ▽ﾟ)ノ"],
            "sad": ["(T_T)", "(._.)", "(；ω；)"],
            "angry": ["(╬ Ò﹏Ó)", "(｀ε´)", "(ノへ￣、)"],
            "surprised": ["(°o°)", "(⊙_⊙)", "Σ(°△°|||)"],
            "neutral": ["(・_・)", "(・ω・)", "(-_-)"],
        }
        idx = min(int(intensity * 3), 2) if intensity > 0.3 else 0
        return symbols.get(emotion, symbols["neutral"])[idx]

    def _print_help(self) -> None:
        print("\n可用指令:")
        for cmd, desc in self.COMMANDS.items():
            print(f"  {cmd:<12} - {desc}")

    def _print_welcome(self) -> None:
        print("""
╭──────────────────────────────────────────╮
│       rubsgame AI 对话系统               │
│  输入 /help 查看指令，输入 /exit 退出    │
╰──────────────────────────────────────────╯
""")
