"""HTTP request metrics middleware.

Records request count (with status code) and request duration per route into
the Prometheus registry. The route *template* (e.g. ``/v1/incidents/{id}``) is
used as the ``path`` label to keep cardinality bounded; unmatched requests are
bucketed under ``<unmatched>``. The ``/metrics`` scrape endpoint itself is not
recorded.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.observability import metrics

_SKIP_PATHS = {"/metrics", "/nexora-api/metrics"}


def _route_label(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if path:
        return path
    return "<unmatched>"


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not metrics.METRICS_AVAILABLE or request.url.path in _SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            duration = time.perf_counter() - start
            metrics.record_request(
                method=request.method,
                path=_route_label(request),
                status=status,
                duration=duration,
            )
