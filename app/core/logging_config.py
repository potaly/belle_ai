"""Logging configuration with trace_id support and file rotation.

企业级日志配置：
- 按天滚动生成日志文件（info 和 error 分离）
- 支持 trace_id 链路追踪
- 同时输出到文件和控制台
"""
from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path
from typing import Optional

from app.core.config import get_settings
from app.core.trace_context import get_trace_id

settings = get_settings()


class TraceIdFilter(logging.Filter):
    """日志过滤器：为每条 LogRecord 注入 trace_id。"""

    def filter(self, record: logging.LogRecord) -> bool:
        """注入 trace_id 到 LogRecord。"""
        trace_id = get_trace_id()
        record.trace_id = trace_id if trace_id else "N/A"
        return True


class ErrorOnlyFilter(logging.Filter):
    """日志过滤器：只允许 ERROR 及以上级别通过。"""

    def filter(self, record: logging.LogRecord) -> bool:
        """只允许 ERROR 及以上级别。"""
        return record.levelno >= logging.ERROR


def init_logging() -> None:
    """
    初始化日志系统。
    
    配置：
    - info 日志文件：app-info-YYYY-MM-DD.log（INFO 及以上）
    - error 日志文件：app-error-YYYY-MM-DD.log（ERROR 及以上）
    - 控制台输出：INFO 及以上
    - 日志格式：时间、级别、trace_id、模块、行号、消息
    """
    # 获取日志目录配置
    log_dir = Path(settings.log_dir if hasattr(settings, "log_dir") else "logs")
    log_backup_count = (
        settings.log_backup_count if hasattr(settings, "log_backup_count") else 14
    )

    # 创建日志目录
    log_dir.mkdir(parents=True, exist_ok=True)

    # 获取根 logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # 根 logger 设置为 DEBUG，由 handler 控制级别

    # 清除已有的 handlers（避免重复）
    root_logger.handlers.clear()

    # 日志格式：时间、级别、trace_id、模块、行号、消息
    log_format = (
        "%(asctime)s %(levelname)s [trace_id=%(trace_id)s] "
        "%(name)s:%(lineno)d - %(message)s"
    )
    formatter = logging.Formatter(
        fmt=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 1. Info 日志文件处理器（INFO 及以上）
    info_handler = logging.handlers.TimedRotatingFileHandler(
        filename=str(log_dir / "app-info.log"),  # 初始文件名
        when="midnight",  # 每天午夜滚动
        interval=1,  # 间隔1天
        backupCount=log_backup_count,  # 保留天数
        encoding="utf-8",
    )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)
    info_handler.addFilter(TraceIdFilter())
    # TimedRotatingFileHandler 会自动在文件名后添加日期后缀（如：app-info.log.2024-12-23）
    # 但我们需要 app-info-2024-12-23.log 格式，所以使用 namer 自定义
    def info_namer(name: str) -> str:
        """自定义 info 日志文件名格式：app-info-YYYY-MM-DD.log"""
        import re
        from datetime import datetime
        # 匹配 app-info.log.2024-12-23 格式
        match = re.match(r"(.+\.log)\.(\d{4}-\d{2}-\d{2})", name)
        if match:
            base, date = match.groups()
            return f"{base.replace('.log', '')}-{date}.log"
        return name
    info_handler.namer = info_namer
    root_logger.addHandler(info_handler)

    # 2. Error 日志文件处理器（ERROR 及以上）
    error_handler = logging.handlers.TimedRotatingFileHandler(
        filename=str(log_dir / "app-error.log"),  # 初始文件名
        when="midnight",
        interval=1,
        backupCount=log_backup_count,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    error_handler.addFilter(TraceIdFilter())
    error_handler.addFilter(ErrorOnlyFilter())  # 只记录 ERROR 及以上
    # 自定义 error 日志文件名格式：app-error-YYYY-MM-DD.log
    def error_namer(name: str) -> str:
        """自定义 error 日志文件名格式：app-error-YYYY-MM-DD.log"""
        import re
        from datetime import datetime
        match = re.match(r"(.+\.log)\.(\d{4}-\d{2}-\d{2})", name)
        if match:
            base, date = match.groups()
            return f"{base.replace('.log', '')}-{date}.log"
        return name
    error_handler.namer = error_namer
    root_logger.addHandler(error_handler)

    # 3. 控制台处理器（INFO 及以上）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(TraceIdFilter())
    root_logger.addHandler(console_handler)

    # 记录初始化日志
    logger = logging.getLogger(__name__)
    logger.info(
        f"Logging initialized: log_dir={log_dir}, "
        f"backup_count={log_backup_count}, "
        f"info_file={log_dir / 'app-info.log'}, "
        f"error_file={log_dir / 'app-error.log'}"
    )

