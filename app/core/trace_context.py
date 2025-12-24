"""Trace ID context management using contextvars (coroutine-safe).

实现类似 MDC 的 trace_id 管理，保证协程并发安全。
"""
from __future__ import annotations

import contextvars
import uuid
from typing import Optional

# 使用 contextvars 存储 trace_id（协程安全）
_trace_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "trace_id", default=None
)


def get_trace_id() -> Optional[str]:
    """
    获取当前上下文的 trace_id。
    
    Returns:
        当前 trace_id，如果不存在则返回 None
    """
    return _trace_id_var.get()


def set_trace_id(trace_id: Optional[str]) -> None:
    """
    设置当前上下文的 trace_id。
    
    Args:
        trace_id: 追踪ID，如果为 None 则清除
    """
    if trace_id:
        _trace_id_var.set(trace_id)
    else:
        # contextvars 不支持直接删除，设置为 None
        _trace_id_var.set(None)


def clear_trace_id() -> None:
    """清除当前上下文的 trace_id。"""
    _trace_id_var.set(None)


def generate_trace_id() -> str:
    """
    生成新的 trace_id。
    
    Returns:
        格式：uuid4 hex 前16位 + 时间戳后6位
    """
    import time
    uuid_part = uuid.uuid4().hex[:16]
    timestamp_part = str(int(time.time()))[-6:]
    return f"{uuid_part}{timestamp_part}"

