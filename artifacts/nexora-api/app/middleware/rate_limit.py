"""Distributed rate-limiting middleware.

Throttles abuse-prone endpoints using a shared sliding window (see
:mod:`app.security.rate_limit`). Limits are applied per identity scope:

* ``ip``   - the client address (honouring ``X-Forwarded-For`` when trusted).
* ``user`` - the authenticated subject decoded from the bearer token.
* ``org``  - the ``organization_id`` claim decoded from the bearer token.

Each in-scope identity is checked independently and the most restrictive scope
wins. When a limit is exceeded the request is rejected with **HTTP 429** and the
standard ``Retry-After`` / ``X-RateLimit-*`` headers.

Endpoints covered (matched by path suffix so the BASE_PATH/``/v1`` prefixes do
not matter):

* ``POST /auth/login``           - per IP
* ``POST /auth/register``        - per IP
* ``POST /auth/refresh``         - per IP + per user
* ``POST /integrations/connect`` - per IP + per user + per organization
* webhook ingestion (``/monitoring/ingest`` and any ``/webhooks/...``) - per IP
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.security.rate_limit import (
    RateLimit,
    RateLimitBackend,
    RateLimitResult,
    get_rate_limit_backend,
    parse_rate,
)

logger = logging.getLogger(__name__)

Scope = str  # one of "ip", "user", "org"


@dataclass(frozen=True)
class RateLimitRule:
    name: str
    methods: frozenset[str]
    scopes: tuple[Scope, ...]
    rate: RateLimit
    # Path suffixes that select this rule (e.g. "/auth/login").
    suffixes: tuple[str, ...]
    # Substrings that also select this rule (e.g. "/webhooks/").
    contains: tuple[str, ...] = ()

    def matches(self, method: str, path: str) -> bool:
        if method.upper() not in self.methods:
            return False
        if any(path.endswith(sfx) for sfx in self.suffixes):
            return True
        return any(part in path for part in self.contains)


def default_rules() -> list[RateLimitRule]:
    """Build the default rule set from application settings."""
    from app.core.config import settings

    return [
        RateLimitRule(
            name="auth_login",
            methods=frozenset({"POST"}),
            scopes=("ip",),
            rate=parse_rate(settings.RATE_LIMIT_AUTH_LOGIN),
            suffixes=("/auth/login",),
        ),
        RateLimitRule(
            name="auth_register",
            methods=frozenset({"POST"}),
            scopes=("ip",),
            rate=parse_rate(settings.RATE_LIMIT_AUTH_REGISTER),
            suffixes=("/auth/register",),
        ),
        RateLimitRule(
            name="auth_refresh",
            methods=frozenset({"POST"}),
            scopes=("ip", "user"),
            rate=parse_rate(settings.RATE_LIMIT_AUTH_REFRESH),
            suffixes=("/auth/refresh",),
        ),
        RateLimitRule(
            name="integrations_connect",
            methods=frozenset({"POST"}),
            scopes=("ip", "user", "org"),
            rate=parse_rate(settings.RATE_LIMIT_INTEGRATIONS_CONNECT),
            suffixes=("/integrations/connect",),
        ),
        RateLimitRule(
            name="webhooks",
            methods=frozenset({"POST"}),
            scopes=("ip",),
            rate=parse_rate(settings.RATE_LIMIT_WEBHOOKS),
            suffixes=("/monitoring/ingest",),
            contains=("/webhooks/",),
        ),
        RateLimitRule(
            name="api_org",
            methods=frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"}),
            scopes=("org",),
            rate=parse_rate(settings.RATE_LIMIT_API_ORG),
            suffixes=(),
            contains=("/v1/",),
        ),
    ]


def _client_ip(request: Request, trust_forwarded_for: bool) -> str:
    if trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Left-most entry is the original client per convention.
            first = forwarded.split(",")[0].strip()
            if first:
                return first
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _identity_from_token(request: Request) -> tuple[str | None, str | None]:
    """Best-effort (user_id, org_id) from the bearer token; never raises."""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        # Fall back to an explicit org header if present (some clients send it).
        return None, request.headers.get("x-organization-id")
    token = auth[7:].strip()
    if not token:
        return None, request.headers.get("x-organization-id")
    try:
        from app.core.security import decode_token

        payload = decode_token(token)
    except Exception:
        return None, request.headers.get("x-organization-id")
    user_id = payload.get("sub")
    org_id = payload.get("organization_id") or request.headers.get("x-organization-id")
    return (str(user_id) if user_id else None), (str(org_id) if org_id else None)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        enabled: bool | None = None,
        key_prefix: str | None = None,
        trust_forwarded_for: bool | None = None,
        fail_open: bool | None = None,
        rules: list[RateLimitRule] | None = None,
        backend: RateLimitBackend | None = None,
    ) -> None:
        super().__init__(app)
        from app.core.config import settings

        self.enabled = settings.RATE_LIMIT_ENABLED if enabled is None else enabled
        self.key_prefix = (
            settings.RATE_LIMIT_KEY_PREFIX if key_prefix is None else key_prefix
        )
        self.trust_forwarded_for = (
            settings.RATE_LIMIT_TRUST_FORWARDED_FOR
            if trust_forwarded_for is None
            else trust_forwarded_for
        )
        self.fail_open = (
            settings.RATE_LIMIT_FAIL_OPEN if fail_open is None else fail_open
        )
        self.rules = default_rules() if rules is None else rules
        self._backend = backend

    async def _get_backend(self) -> RateLimitBackend:
        if self._backend is not None:
            return self._backend
        return await get_rate_limit_backend()

    def _scope_identities(
        self, request: Request, rule: RateLimitRule
    ) -> list[tuple[Scope, str]]:
        identities: list[tuple[Scope, str]] = []
        user_id: str | None = None
        org_id: str | None = None
        if "user" in rule.scopes or "org" in rule.scopes:
            user_id, org_id = _identity_from_token(request)
        for scope in rule.scopes:
            if scope == "ip":
                identities.append(("ip", _client_ip(request, self.trust_forwarded_for)))
            elif scope == "user" and user_id:
                identities.append(("user", user_id))
            elif scope == "org" and org_id:
                identities.append(("org", org_id))
        return identities

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not self.enabled:
            return await call_next(request)

        rule = next(
            (r for r in self.rules if r.matches(request.method, request.url.path)),
            None,
        )
        if rule is None:
            return await call_next(request)

        identities = self._scope_identities(request, rule)
        if not identities:
            return await call_next(request)

        backend = await self._get_backend()
        blocked: tuple[Scope, RateLimitResult] | None = None
        tightest: RateLimitResult | None = None
        for scope, identity in identities:
            key = f"{self.key_prefix}:{rule.name}:{scope}:{identity}"
            try:
                result = await backend.hit(key, rule.rate.limit, rule.rate.window)
            except Exception as exc:
                # Backend outage: fail open (allow) or closed (block) per config.
                logger.warning(
                    "rate_limit_backend_error",
                    extra={"error": str(exc), "rule": rule.name, "scope": scope},
                )
                if self.fail_open:
                    return await call_next(request)
                return self._too_many(rule, scope, None)
            if not result.allowed:
                if blocked is None or result.retry_after > blocked[1].retry_after:
                    blocked = (scope, result)
            if tightest is None or result.remaining < tightest.remaining:
                tightest = result

        if blocked is not None:
            scope, result = blocked
            logger.info(
                "rate_limit_exceeded",
                extra={
                    "rule": rule.name,
                    "scope": scope,
                    "path": request.url.path,
                    "limit": result.limit,
                },
            )
            return self._too_many(rule, scope, result)

        response = await call_next(request)
        if tightest is not None:
            self._apply_headers(response, tightest)
        return response

    def _too_many(
        self, rule: RateLimitRule, scope: Scope, result: RateLimitResult | None
    ) -> JSONResponse:
        retry_after = result.retry_after if result is not None else rule.rate.window
        response = JSONResponse(
            status_code=429,
            content={
                "detail": "Rate limit exceeded. Please retry later.",
                "scope": scope,
                "limit": rule.rate.limit,
                "window_seconds": rule.rate.window,
                "retry_after": retry_after,
            },
        )
        response.headers["Retry-After"] = str(retry_after)
        response.headers["X-RateLimit-Limit"] = str(rule.rate.limit)
        response.headers["X-RateLimit-Remaining"] = "0"
        response.headers["X-RateLimit-Reset"] = str(retry_after)
        response.headers["X-RateLimit-Scope"] = scope
        return response

    @staticmethod
    def _apply_headers(response: Response, result: RateLimitResult) -> None:
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(int(result.reset_after + 0.999))
