"""FastAPI middleware for trace_id propagation and access logging."""
from __future__ import annotations

import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.trace_context import (
    clear_trace_id,
    generate_trace_id,
    get_trace_id,
    set_trace_id,
)

logger = logging.getLogger(__name__)


class TraceIdMiddleware(BaseHTTPMiddleware):
    """Trace ID 中间件：处理请求头 X-Trace-Id，并在响应头返回。"""

    def __init__(self, app: ASGIApp) -> None:
        """
        初始化中间件。
        
        Args:
            app: ASGI 应用实例
        """
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        处理请求：提取/生成 trace_id，设置到上下文，记录 access log。
        
        Args:
            request: FastAPI 请求对象
            call_next: 下一个中间件或路由处理器
        
        Returns:
            FastAPI 响应对象
        """
        # 1. 提取或生成 trace_id
        trace_id_header = request.headers.get("X-Trace-Id") or request.headers.get(
            "x-trace-id"
        )
        trace_id = trace_id_header if trace_id_header else generate_trace_id()

        # 2. 设置到上下文
        set_trace_id(trace_id)

        # 3. 记录请求开始时间
        start_time = time.time()

        # 4. 获取客户端 IP
        client_ip = request.client.host if request.client else "unknown"

        try:
            # 5. 调用下一个中间件或路由处理器
            response = await call_next(request)

            # 6. 计算耗时
            latency_ms = int((time.time() - start_time) * 1000)

            # 7. 在响应头返回 trace_id
            response.headers["X-Trace-Id"] = trace_id

            # 8. 记录 access log（成功）
            logger.info(
                f"ACCESS {request.method} {request.url.path} "
                f"status={response.status_code} "
                f"latency_ms={latency_ms} "
                f"client_ip={client_ip} "
                f"trace_id={trace_id}"
            )

            return response

        except Exception as e:
            # 9. 计算耗时（异常情况）
            latency_ms = int((time.time() - start_time) * 1000)

            # 10. 记录 access log（异常）
            logger.error(
                f"ACCESS {request.method} {request.url.path} "
                f"status=500 "
                f"latency_ms={latency_ms} "
                f"client_ip={client_ip} "
                f"trace_id={trace_id} "
                f"error={str(e)}",
                exc_info=True,  # 包含异常堆栈
            )

            # 11. 重新抛出异常（让 FastAPI 的错误处理器处理）
            raise

        finally:
            # 12. 清理上下文（避免泄漏）
            clear_trace_id()

