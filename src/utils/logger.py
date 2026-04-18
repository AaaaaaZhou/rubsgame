"""
日志系统模块
支持多Logger实例、文件与控制台输出、按模块名称空间区分
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from typing import Dict

COLOR_CODES = {
    'DEBUG': '\033[36m',
    'INFO': '\033[32m',
    'WARNING': '\033[33m',
    'ERROR': '\033[31m',
    'CRITICAL': '\033[35m',
    'RESET': '\033[0m'
}

LOGGER_NAMESPACES = {
    "MAIN": "rubsgame.main",
    "EMOTION": "rubsgame.emotion",
    "MEMORY": "rubsgame.memory",
    "SESSION": "rubsgame.session",
    "WORLD": "rubsgame.world",
    "PERSONA": "rubsgame.persona",
    "LLM": "rubsgame.llm",
    "INTERFACE": "rubsgame.interface"
}

_default_config = {
    "log_file": "data/logs/runtime.log",
    "level": "INFO",
    "max_file_size": 10 * 1024 * 1024,
    "backup_count": 5,
    "enable_console": True,
    "enable_file": True
}

_loggers: Dict[str, logging.Logger] = {}


def _supports_ansi() -> bool:
    if sys.platform != "win32":
        return True
    return os.getenv("TERM") not in (None, "", "dumb")


class ColoredFormatter(logging.Formatter):
    def format(self, record):
        log_message = super().format(record)
        if _supports_ansi() and record.levelname in COLOR_CODES:
            return f"{COLOR_CODES[record.levelname]}{log_message}{COLOR_CODES['RESET']}"
        return log_message


def _setup_logger(
    name: str,
    log_file: str,
    level: str,
    max_file_size: int,
    backup_count: int,
    enable_console: bool,
    enable_file: bool
) -> logging.Logger:
    """配置并返回Logger实例"""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)

    file_formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_formatter = ColoredFormatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    if enable_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger


def get_logger(namespace: str, **kwargs) -> logging.Logger:
    """获取指定名称空间的Logger

    Args:
        namespace: Logger名称空间
        **kwargs: 覆盖默认配置

    Returns:
        Logger实例
    """
    if namespace in _loggers:
        return _loggers[namespace]

    config = _default_config.copy()
    config.update(kwargs)

    logger = _setup_logger(
        name=namespace,
        log_file=config["log_file"],
        level=config["level"],
        max_file_size=config["max_file_size"],
        backup_count=config["backup_count"],
        enable_console=config["enable_console"],
        enable_file=config["enable_file"]
    )

    _loggers[namespace] = logger
    return logger


class LoggerFactory:
    """Logger工厂类，管理各模块的Logger实例"""

    @classmethod
    def get_logger(cls, namespace: str, **kwargs) -> logging.Logger:
        return get_logger(namespace, **kwargs)

    @classmethod
    def get_emotion_logger(cls) -> logging.Logger:
        return get_logger(LOGGER_NAMESPACES["EMOTION"])

    @classmethod
    def get_memory_logger(cls) -> logging.Logger:
        return get_logger(LOGGER_NAMESPACES["MEMORY"])

    @classmethod
    def get_session_logger(cls) -> logging.Logger:
        return get_logger(LOGGER_NAMESPACES["SESSION"])

    @classmethod
    def get_llm_logger(cls) -> logging.Logger:
        return get_logger(LOGGER_NAMESPACES["LLM"])

    @classmethod
    def update_default_config(cls, **kwargs):
        _default_config.update(kwargs)


def get_emotion_logger() -> logging.Logger:
    return LoggerFactory.get_emotion_logger()


def get_memory_logger() -> logging.Logger:
    return LoggerFactory.get_memory_logger()


def get_session_logger() -> logging.Logger:
    return LoggerFactory.get_session_logger()


def get_llm_logger() -> logging.Logger:
    return LoggerFactory.get_llm_logger()


default_logger = get_logger("rubsgame")
