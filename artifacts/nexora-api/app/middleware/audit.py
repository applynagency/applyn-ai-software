import time
import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.monotonic()
        logger = structlog.get_logger(__name__)

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            path=request.url.path,
            method=request.method,
        )

        response = await call_next(request)

        duration_ms = round((time.monotonic() - start_time) * 1000, 2)

        structlog.contextvars.bind_contextvars(
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        logger.info("http_request")

        return response
