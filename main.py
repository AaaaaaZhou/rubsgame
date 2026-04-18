#!/usr/bin/env python3
"""
rubsgame - AI 对话系统入口
"""
import sys
import argparse

from src.core.engine import EngineCore
from src.interface.ps_shell import PowerShellInterface
from src.utils.config import AppConfig
from src.utils.logger import get_logger

_logger = get_logger("rubsgame.main")


def parse_args():
    parser = argparse.ArgumentParser(description="rubsgame AI 对话系统")
    parser.add_argument("--persona", "-p", type=str, help="启动时加载的人设名称")
    parser.add_argument("--world", "-w", type=str, help="启动时加载的世界观名称")
    parser.add_argument("--session", "-s", type=str, default="default", help="会话 ID")
    parser.add_argument("--model", "-m", type=str, help="指定 LLM 模型")
    return parser.parse_args()


def main():
    args = parse_args()

    # 初始化配置
    config = AppConfig.get_instance()

    # 可选：指定模型
    if args.model:
        config.set_current_llm_model(args.model)

    # 初始化引擎
    engine = EngineCore(config)

    # 可选：预加载资源和会话
    if args.persona:
        try:
            engine.load_persona(args.persona)
        except Exception as e:
            print(f"[Warning] 无法加载人设 {args.persona}: {e}")

    if args.world:
        try:
            engine.load_world(args.world)
        except Exception as e:
            print(f"[Warning] 无法加载世界观 {args.world}: {e}")

    # 启动 REPL
    shell = PowerShellInterface(engine)
    shell.run_repl()


if __name__ == "__main__":
    main()
