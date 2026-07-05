"""Tests for the enterprise HTTP security-headers middleware.

Builds isolated FastAPI apps (no DB) with the middleware and asserts the headers,
production/development differences, the relaxed docs CSP (Swagger UI not broken),
and Cache-Control behavior.
"""

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response

from app.middleware.security_headers import SecurityHeadersMiddleware

BASE = "/nexora-api"


def _make_app(*, production: bool = False, enabled: bool = True) -> FastAPI:
    app = FastAPI(docs_url=f"{BASE}/docs", redoc_url=f"{BASE}/redoc", openapi_url=f"{BASE}/openapi.json")
    app.add_middleware(
        SecurityHeadersMiddleware,
        production=production,
        base_path=BASE,
        enabled=enabled,
        hsts_max_age=63072000,
    )

    @app.get(f"{BASE}/v1/ping")
    async def ping():
        return JSONResponse({"ok": True})

    @app.get(f"{BASE}/v1/cached")
    async def cached():
        return JSONResponse({"ok": True}, headers={"Cache-Control": "public, max-age=60"})

    @app.get("/app.js")
    async def dashboard_asset():
        return Response("console.log(1)", media_type="application/javascript")

    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_core_headers_present():
    async with _client(_make_app()) as c:
        r = await c.get(f"{BASE}/v1/ping")
    assert r.status_code == 200
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "geolocation=()" in r.headers["Permissions-Policy"]
    assert "camera=()" in r.headers["Permissions-Policy"]
    assert r.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert "Content-Security-Policy" in r.headers


async def test_app_csp_is_strict():
    async with _client(_make_app()) as c:
        r = await c.get(f"{BASE}/v1/ping")
    csp = r.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert "script-src 'self'" in csp and "cdn.jsdelivr.net" not in csp
    # SPA inline styles are permitted; inline scripts are NOT.
    assert "style-src 'self' 'unsafe-inline'" in csp
    assert "'unsafe-inline' https://cdn.jsdelivr.net" not in csp


async def test_production_emits_hsts_and_upgrade():
    async with _client(_make_app(production=True)) as c:
        r = await c.get(f"{BASE}/v1/ping")
    assert r.headers["Strict-Transport-Security"] == "max-age=63072000; includeSubDomains; preload"
    assert "upgrade-insecure-requests" in r.headers["Content-Security-Policy"]


async def test_development_omits_hsts_and_allows_ws():
    async with _client(_make_app(production=False)) as c:
        r = await c.get(f"{BASE}/v1/ping")
    assert "Strict-Transport-Security" not in r.headers
    csp = r.headers["Content-Security-Policy"]
    assert "upgrade-insecure-requests" not in csp
    assert "connect-src 'self' ws: wss:" in csp


async def test_docs_csp_is_relaxed_and_swagger_not_broken():
    async with _client(_make_app()) as c:
        r = await c.get(f"{BASE}/docs")
    assert r.status_code == 200
    # FastAPI's real Swagger UI HTML is returned...
    assert "swagger-ui" in r.text.lower()
    # ...and the CSP permits its CDN assets + inline bootstrap script.
    csp = r.headers["Content-Security-Policy"]
    assert "https://cdn.jsdelivr.net" in csp
    assert "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net" in csp
    assert "worker-src 'self' blob:" in csp  # ReDoc/Swagger workers


async def test_redoc_gets_relaxed_csp():
    async with _client(_make_app()) as c:
        r = await c.get(f"{BASE}/redoc")
    assert r.status_code == 200
    assert "https://fonts.gstatic.com" in r.headers["Content-Security-Policy"]


async def test_cache_control_no_store_on_api():
    async with _client(_make_app()) as c:
        r = await c.get(f"{BASE}/v1/ping")
    assert r.headers["Cache-Control"] == "no-store"


async def test_cache_control_not_overwritten_when_route_sets_it():
    async with _client(_make_app()) as c:
        r = await c.get(f"{BASE}/v1/cached")
    assert r.headers["Cache-Control"] == "public, max-age=60"


async def test_cache_control_not_forced_on_dashboard_assets():
    # Paths outside the API base_path (the served dashboard) keep their own
    # caching policy; the middleware must not stamp no-store on them.
    async with _client(_make_app()) as c:
        r = await c.get("/app.js")
    assert r.headers.get("Cache-Control") != "no-store"
    # But security headers still apply to the dashboard.
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in r.headers


async def test_disabled_is_passthrough():
    async with _client(_make_app(enabled=False)) as c:
        r = await c.get(f"{BASE}/v1/ping")
    assert r.status_code == 200
    for h in ("Content-Security-Policy", "X-Frame-Options", "X-Content-Type-Options",
              "Referrer-Policy", "Permissions-Policy", "Strict-Transport-Security"):
        assert h not in r.headers
