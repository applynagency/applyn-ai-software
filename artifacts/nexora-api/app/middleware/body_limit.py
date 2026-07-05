"""Global request body size limits.

Rejects oversized request payloads with **HTTP 413** before they can be buffered
into memory by a route handler — a basic but important DoS protection.

The limit is selected by ``Content-Type``:

* ``multipart/*`` (file uploads) -> ``MAX_MULTIPART_BODY_BYTES`` (default 100 MB)
* everything else (JSON, form, text) -> ``MAX_JSON_BODY_BYTES`` (default 5 MB)

Individual routes can override the limit by registering a path suffix with
:func:`set_route_body_limit` (or by passing ``route_overrides`` to the
middleware). The longest matching suffix wins.

Enforcement is two-layered:

1. **``Content-Length`` fast path** — well-behaved clients send the length, so
   the request is rejected immediately without reading a single body byte.
2. **Streaming guard** — for chunked / missing / spoofed ``Content-Length`` the
   body bytes are counted as they are pulled by the route, and the request is
   aborted with 413 the moment the limit is crossed.

This is implemented as a pure-ASGI middleware so it can wrap ``receive`` and
short-circuit cleanly without consuming the body on the fast path.
"""

from __future__ import annotations

import json
import logging

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

# Process-wide per-route overrides, keyed by path suffix -> max bytes. Routes or
# startup code may populate this via set_route_body_limit().
ROUTE_BODY_LIMITS: dict[str, int] = {}


def set_route_body_limit(path_suffix: str, max_bytes: int) -> None:
    """Register a per-route body-size override (matched by path suffix)."""
    if max_bytes <= 0:
        raise ValueError("max_bytes must be > 0")
    ROUTE_BODY_LIMITS[path_suffix] = max_bytes


def clear_route_body_limits() -> None:
    """Remove all registered per-route overrides (used by tests)."""
    ROUTE_BODY_LIMITS.clear()


class _PayloadTooLarge(Exception):
    def __init__(self, limit: int) -> None:
        self.limit = limit


class BodyLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        json_limit: int | None = None,
        multipart_limit: int | None = None,
        enabled: bool | None = None,
        route_overrides: dict[str, int] | None = None,
    ) -> None:
        self.app = app
        from app.core.config import settings

        self.json_limit = (
            settings.MAX_JSON_BODY_BYTES if json_limit is None else json_limit
        )
        self.multipart_limit = (
            settings.MAX_MULTIPART_BODY_BYTES
            if multipart_limit is None
            else multipart_limit
        )
        self.enabled = settings.BODY_LIMIT_ENABLED if enabled is None else enabled
        self.route_overrides = route_overrides or {}

    def _limit_for(self, path: str, content_type: str) -> int:
        # Per-route override (longest matching suffix wins). Constructor overrides
        # take precedence over the global registry for the same suffix.
        merged = {**ROUTE_BODY_LIMITS, **self.route_overrides}
        best: tuple[str, int] | None = None
        for suffix, limit in merged.items():
            if path.endswith(suffix) and (best is None or len(suffix) > len(best[0])):
                best = (suffix, limit)
        if best is not None:
            return best[1]
        if content_type.lower().startswith("multipart/"):
            return self.multipart_limit
        return self.json_limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.enabled:
            await self.app(scope, receive, send)
            return

        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        content_type = headers.get(b"content-type", b"").decode("latin-1")
        limit = self._limit_for(scope.get("path", ""), content_type)

        # Fast path: trust an explicit Content-Length when present.
        raw_len = headers.get(b"content-length")
        if raw_len is not None:
            try:
                declared = int(raw_len)
            except ValueError:
                declared = None
            if declared is not None and declared > limit:
                await self._reject(send, limit)
                return

        # Streaming guard for chunked / missing / understated Content-Length.
        body_size = 0

        async def limited_receive() -> Message:
            nonlocal body_size
            message = await receive()
            if message["type"] == "http.request":
                body_size += len(message.get("body", b""))
                if body_size > limit:
                    raise _PayloadTooLarge(limit)
            return message

        response_started = False

        async def wrapped_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, wrapped_send)
        except _PayloadTooLarge as exc:
            if response_started:
                # Response already in flight; cannot rewrite to 413.
                raise
            await self._reject(send, exc.limit)

    @staticmethod
    async def _reject(send: Send, limit: int) -> None:
        body = json.dumps(
            {
                "detail": "Request payload too large.",
                "max_bytes": limit,
            }
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("latin-1")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
        logger.info("request_body_too_large", extra={"max_bytes": limit})
