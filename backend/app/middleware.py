"""跨路由请求上下文：统一关联日志、错误响应和客户端请求。"""

import logging
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response
from fastapi.responses import JSONResponse


logger = logging.getLogger(__name__)


async def request_context_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """为每个请求生成追踪 ID，并将未处理异常收敛为不泄露内部细节的响应。"""
    request_id = uuid4().hex
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled request error", extra={"request_id": request_id})
        response = JSONResponse(
            status_code=500,
            content={"detail": "服务器内部错误", "request_id": request_id},
        )
    response.headers["X-Request-ID"] = request_id
    return response
