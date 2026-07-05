"""Integration tests for the distributed rate-limiting middleware.

Builds isolated FastAPI apps (no DB) wired with ``RateLimitMiddleware`` over an
in-memory backend and exercises per-IP / per-user / per-organization scoping,
the HTTP 429 response + headers, scope isolation, fail-open/closed behaviour and
that non-listed endpoints are untouched.
"""

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.core.security import create_access_token
from app.middleware.rate_limit import RateLimitMiddleware, RateLimitRule
from app.security.rate_limit import InMemoryRateLimitBackend, RateLimitResult, parse_rate

BASE = "/nexora-api"


def _rules() -> list[RateLimitRule]:
    return [
        RateLimitRule(
            name="auth_login",
            methods=frozenset({"POST"}),
            scopes=("ip",),
            rate=parse_rate("2/60"),
            suffixes=("/auth/login",),
        ),
        RateLimitRule(
            name="integrations_connect",
            methods=frozenset({"POST"}),
            scopes=("ip", "user", "org"),
            rate=parse_rate("2/60"),
            suffixes=("/integrations/connect",),
        ),
        RateLimitRule(
            name="webhooks",
            methods=frozenset({"POST"}),
            scopes=("ip",),
            rate=parse_rate("2/60"),
            suffixes=("/monitoring/ingest",),
            contains=("/webhooks/",),
        ),
    ]


def _make_app(*, enabled: bool = True, backend=None, fail_open: bool = True) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        enabled=enabled,
        trust_forwarded_for=True,
        fail_open=fail_open,
        rules=_rules(),
        backend=backend if backend is not None else InMemoryRateLimitBackend(),
    )

    @app.post(f"{BASE}/v1/auth/login")
    async def login():
        return JSONResponse({"ok": True})

    @app.post(f"{BASE}/v1/integrations/connect")
    async def connect():
        return JSONResponse({"ok": True})

    @app.post(f"{BASE}/v1/monitoring/ingest")
    async def ingest():
        return JSONResponse({"ok": True})

    @app.post(f"{BASE}/v1/webhooks/github")
    async def webhook_github():
        return JSONResponse({"ok": True})

    @app.post(f"{BASE}/v1/auth/logout")
    async def logout():
        return JSONResponse({"ok": True})

    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def _bearer(user_id: str, org_id: str | None = None) -> dict[str, str]:
    extra = {"organization_id": org_id} if org_id else None
    token = create_access_token(user_id, extra=extra)
    return {"Authorization": f"Bearer {token}"}


async def test_login_limited_per_ip_returns_429():
    async with _client(_make_app()) as c:
        h = {"X-Forwarded-For": "1.1.1.1"}
        r1 = await c.post(f"{BASE}/v1/auth/login", headers=h)
        r2 = await c.post(f"{BASE}/v1/auth/login", headers=h)
        r3 = await c.post(f"{BASE}/v1/auth/login", headers=h)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
    assert r3.json()["scope"] == "ip"
    assert int(r3.headers["Retry-After"]) >= 1
    assert r3.headers["X-RateLimit-Limit"] == "2"
    assert r3.headers["X-RateLimit-Remaining"] == "0"
    assert r3.headers["X-RateLimit-Scope"] == "ip"


async def test_rate_limit_headers_on_allowed_requests():
    async with _client(_make_app()) as c:
        r = await c.post(f"{BASE}/v1/auth/login", headers={"X-Forwarded-For": "9.9.9.9"})
    assert r.status_code == 200
    assert r.headers["X-RateLimit-Limit"] == "2"
    assert r.headers["X-RateLimit-Remaining"] == "1"
    assert "X-RateLimit-Reset" in r.headers


async def test_different_ips_have_independent_windows():
    async with _client(_make_app()) as c:
        for _ in range(2):
            assert (await c.post(f"{BASE}/v1/auth/login", headers={"X-Forwarded-For": "1.1.1.1"})).status_code == 200
        blocked = await c.post(f"{BASE}/v1/auth/login", headers={"X-Forwarded-For": "1.1.1.1"})
        other = await c.post(f"{BASE}/v1/auth/login", headers={"X-Forwarded-For": "2.2.2.2"})
    assert blocked.status_code == 429
    assert other.status_code == 200


async def test_connect_limited_per_user_independent_of_ip():
    # Same user from a brand new IP is still blocked => the user scope, not the
    # IP scope, is what trips. Proves per-user limiting.
    app = _make_app()
    headers_a = _bearer("user-alice")
    async with _client(app) as c:
        r1 = await c.post(f"{BASE}/v1/integrations/connect", headers={**headers_a, "X-Forwarded-For": "10.0.0.1"})
        r2 = await c.post(f"{BASE}/v1/integrations/connect", headers={**headers_a, "X-Forwarded-For": "10.0.0.1"})
        r3 = await c.post(f"{BASE}/v1/integrations/connect", headers={**headers_a, "X-Forwarded-For": "10.0.0.99"})
        # A different user from the same fresh IP is allowed.
        r4 = await c.post(f"{BASE}/v1/integrations/connect", headers={**_bearer("user-bob"), "X-Forwarded-For": "10.0.0.99"})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
    assert r3.json()["scope"] == "user"
    assert r4.status_code == 200


async def test_connect_limited_per_organization():
    app = _make_app()
    async with _client(app) as c:
        # Two different users in the same org, each from its own IP: only the org
        # scope accumulates, so the third request is blocked on "org".
        r1 = await c.post(f"{BASE}/v1/integrations/connect", headers={**_bearer("u1", "org-1"), "X-Forwarded-For": "11.0.0.1"})
        r2 = await c.post(f"{BASE}/v1/integrations/connect", headers={**_bearer("u2", "org-1"), "X-Forwarded-For": "11.0.0.2"})
        r3 = await c.post(f"{BASE}/v1/integrations/connect", headers={**_bearer("u3", "org-1"), "X-Forwarded-For": "11.0.0.3"})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
    assert r3.json()["scope"] == "org"


async def test_webhook_endpoints_are_limited():
    async with _client(_make_app()) as c:
        h = {"X-Forwarded-For": "5.5.5.5"}
        assert (await c.post(f"{BASE}/v1/monitoring/ingest", headers=h)).status_code == 200
        assert (await c.post(f"{BASE}/v1/monitoring/ingest", headers=h)).status_code == 200
        assert (await c.post(f"{BASE}/v1/monitoring/ingest", headers=h)).status_code == 429


async def test_webhook_contains_match():
    async with _client(_make_app()) as c:
        h = {"X-Forwarded-For": "6.6.6.6"}
        assert (await c.post(f"{BASE}/v1/webhooks/github", headers=h)).status_code == 200
        assert (await c.post(f"{BASE}/v1/webhooks/github", headers=h)).status_code == 200
        assert (await c.post(f"{BASE}/v1/webhooks/github", headers=h)).status_code == 429


async def test_unlisted_endpoint_is_not_limited():
    async with _client(_make_app()) as c:
        h = {"X-Forwarded-For": "7.7.7.7"}
        statuses = [(await c.post(f"{BASE}/v1/auth/logout", headers=h)).status_code for _ in range(6)]
        last = await c.post(f"{BASE}/v1/auth/logout", headers=h)
    assert all(s == 200 for s in statuses)
    assert "X-RateLimit-Limit" not in last.headers


async def test_disabled_middleware_does_not_limit():
    async with _client(_make_app(enabled=False)) as c:
        h = {"X-Forwarded-For": "8.8.8.8"}
        statuses = [(await c.post(f"{BASE}/v1/auth/login", headers=h)).status_code for _ in range(10)]
    assert all(s == 200 for s in statuses)


class _BrokenBackend:
    async def hit(self, key, limit, window) -> RateLimitResult:
        raise RuntimeError("redis down")

    async def reset(self, key) -> None:  # pragma: no cover
        pass

    async def aclose(self) -> None:  # pragma: no cover
        pass


async def test_fail_open_allows_when_backend_errors():
    app = _make_app(backend=_BrokenBackend(), fail_open=True)
    async with _client(app) as c:
        r = await c.post(f"{BASE}/v1/auth/login", headers={"X-Forwarded-For": "1.2.3.4"})
    assert r.status_code == 200


async def test_fail_closed_blocks_when_backend_errors():
    app = _make_app(backend=_BrokenBackend(), fail_open=False)
    async with _client(app) as c:
        r = await c.post(f"{BASE}/v1/auth/login", headers={"X-Forwarded-For": "1.2.3.4"})
    assert r.status_code == 429
