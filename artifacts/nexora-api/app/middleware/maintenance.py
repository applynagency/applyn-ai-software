"""Maintenance-mode middleware (Sprint 62B).

When maintenance mode is on, the API returns ``503 Service Unavailable`` for
business endpoints while keeping the operational surface reachable: health
probes (``/livez`` ``/readyz`` ``/startupz`` ``/metrics``), the docs, and the ops
control endpoints (so the toggle can be turned back off). Disabled by default;
gated by a config-backed flag fronted by a short TTL cache, so the hot path adds
at most one cached lookup.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Always-allowed path fragments even during maintenance.
_ALLOW_FRAGMENTS = (
    "/livez", "/readyz", "/startupz", "/metrics", "/health",
    "/docs", "/redoc", "/openapi.json",
    "/platform/ops",  # ops control plane (toggle maintenance back off)
)


class MaintenanceModeMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, enabled: bool = True) -> None:
        super().__init__(app)
        self._enabled = enabled

    def _is_allowed(self, path: str, method: str) -> bool:
        if method in ("OPTIONS", "HEAD"):
            return True
        return any(frag in path for frag in _ALLOW_FRAGMENTS)

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self._enabled:
            return await call_next(request)

        path = request.url.path
        if self._is_allowed(path, request.method):
            return await call_next(request)

        try:
            from app.database.session import AsyncSessionLocal
            from app.platform.operations import OperationsService

            async with AsyncSessionLocal() as session:
                status = await OperationsService(session).maintenance_status()
        except Exception:  # noqa: BLE001 - never fail closed on a status read error
            status = {"enabled": False}

        if status.get("enabled"):
            return JSONResponse(
                status_code=503,
                content={"detail": status.get("message", "Service under maintenance"),
                         "maintenance": True},
                headers={"Retry-After": "120"},
            )
        return await call_next(request)
