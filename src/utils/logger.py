"""
日志系统模块
支持多Logger实例、文件与控制台输出、按模块名称空间区分
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional, Dict


class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器（用于控制台输出）"""
    
    # 颜色代码
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
        'RESET': '\033[0m'        # 重置
    }
    
    def format(self, record):
        """格式化日志记录，添加颜色"""
        log_message = super().format(record)
        if record.levelname in self.COLORS:
            return f"{self.COLORS[record.levelname]}{log_message}{self.COLORS['RESET']}"
        return log_message


def setup_logger(
    name: str = "rubsgame",
    log_file: str = "data/logs/runtime.log",
    level: str = "INFO",
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    enable_console: bool = True,
    enable_file: bool = True
) -> logging.Logger:
    """
    设置并返回一个配置好的Logger实例
    
    Args:
        name: Logger名称，用于模块区分（如 "EMOTION", "MEMORY"）
        log_file: 日志文件路径
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR)
        max_file_size: 单个日志文件最大大小（字节）
        backup_count: 备份文件数量
        enable_console: 是否启用控制台输出
        enable_file: 是否启用文件输出
    
    Returns:
        logging.Logger: 配置好的Logger实例
    """
    # 创建Logger
    logger = logging.getLogger(name)
    
    # 避免重复添加handler
    if logger.handlers:
        return logger
    
    # 设置日志级别
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # 创建格式化器
    file_formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_formatter = ColoredFormatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # 文件处理器（按大小轮转）
    if enable_file:
        # 确保日志目录存在
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
    
    # 控制台处理器
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    return logger


# 预定义Logger名称空间
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


class LoggerFactory:
    """Logger工厂类，管理各模块的Logger实例"""
    
    _loggers: Dict[str, logging.Logger] = {}
    _default_config = {
        "log_file": "data/logs/runtime.log",
        "level": "INFO",
        "max_file_size": 10 * 1024 * 1024,
        "backup_count": 5,
        "enable_console": True,
        "enable_file": True
    }
    
    @classmethod
    def get_logger(cls, namespace: str, **kwargs) -> logging.Logger:
        """
        获取指定名称空间的Logger
        
        Args:
            namespace: Logger名称空间（可使用预定义或自定义）
            **kwargs: 覆盖默认配置
        
        Returns:
            logging.Logger: Logger实例
        """
        if namespace in cls._loggers:
            return cls._loggers[namespace]
        
        # 合并配置
        config = cls._default_config.copy()
        config.update(kwargs)
        
        # 创建Logger
        logger = setup_logger(
            name=namespace,
            log_file=config["log_file"],
            level=config["level"],
            max_file_size=config["max_file_size"],
            backup_count=config["backup_count"],
            enable_console=config["enable_console"],
            enable_file=config["enable_file"]
        )
        
        cls._loggers[namespace] = logger
        return logger
    
    @classmethod
    def get_emotion_logger(cls) -> logging.Logger:
        """获取情绪引擎专用Logger"""
        return cls.get_logger(LOGGER_NAMESPACES["EMOTION"])
    
    @classmethod
    def get_memory_logger(cls) -> logging.Logger:
        """获取记忆引擎专用Logger"""
        return cls.get_logger(LOGGER_NAMESPACES["MEMORY"])
    
    @classmethod
    def get_session_logger(cls) -> logging.Logger:
        """获取会话管理专用Logger"""
        return cls.get_logger(LOGGER_NAMESPACES["SESSION"])
    
    @classmethod
    def get_llm_logger(cls) -> logging.Logger:
        """获取LLM接入专用Logger"""
        return cls.get_logger(LOGGER_NAMESPACES["LLM"])
    
    @classmethod
    def update_default_config(cls, **kwargs):
        """更新默认Logger配置"""
        cls._default_config.update(kwargs)


# 便捷函数
def get_logger(namespace: str) -> logging.Logger:
    """便捷函数：获取指定名称空间的Logger"""
    return LoggerFactory.get_logger(namespace)


def get_emotion_logger() -> logging.Logger:
    """便捷函数：获取情绪引擎Logger"""
    return LoggerFactory.get_emotion_logger()


def get_memory_logger() -> logging.Logger:
    """便捷函数：获取记忆引擎Logger"""
    return LoggerFactory.get_memory_logger()


def get_session_logger() -> logging.Logger:
    """便捷函数：获取会话管理Logger"""
    return LoggerFactory.get_session_logger()


def get_llm_logger() -> logging.Logger:
    """便捷函数：获取LLM接入Logger"""
    return LoggerFactory.get_llm_logger()


# 初始化默认Logger
default_logger = get_logger("rubsgame")