"""Tests for the global request-body-size middleware (app.middleware.body_limit).

Builds isolated apps (no DB) and exercises the Content-Length fast path, the
streaming guard (chunked / no Content-Length), Content-Type-based limits,
per-route overrides, the 413 body/headers, and the disabled switch.
"""

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.middleware.body_limit import (
    BodyLimitMiddleware,
    clear_route_body_limits,
    set_route_body_limit,
)

# Small limits keep the tests fast: JSON 1 KB, multipart 4 KB.
JSON_LIMIT = 1000
MULTIPART_LIMIT = 4000


def _make_app(*, enabled: bool = True, route_overrides=None) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        BodyLimitMiddleware,
        json_limit=JSON_LIMIT,
        multipart_limit=MULTIPART_LIMIT,
        enabled=enabled,
        route_overrides=route_overrides or {},
    )

    @app.post("/echo")
    async def echo(request: Request):
        body = await request.body()
        return JSONResponse({"len": len(body)})

    @app.post("/big-upload")
    async def big_upload(request: Request):
        body = await request.body()
        return JSONResponse({"len": len(body)})

    @app.post("/tiny")
    async def tiny(request: Request):
        body = await request.body()
        return JSONResponse({"len": len(body)})

    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_small_json_body_allowed():
    async with _client(_make_app()) as c:
        r = await c.post("/echo", content=b"x" * 500, headers={"Content-Type": "application/json"})
    assert r.status_code == 200
    assert r.json()["len"] == 500


async def test_large_json_body_rejected_via_content_length():
    async with _client(_make_app()) as c:
        r = await c.post("/echo", content=b"x" * 2000, headers={"Content-Type": "application/json"})
    assert r.status_code == 413
    payload = r.json()
    assert payload["detail"] == "Request payload too large."
    assert payload["max_bytes"] == JSON_LIMIT
    assert r.headers["content-type"].startswith("application/json")


async def test_multipart_gets_larger_budget_than_json():
    # 2 KB exceeds the JSON limit (1 KB) but is within the multipart limit (4 KB).
    headers = {"Content-Type": "multipart/form-data; boundary=abc"}
    async with _client(_make_app()) as c:
        r = await c.post("/echo", content=b"x" * 2000, headers=headers)
    assert r.status_code == 200
    assert r.json()["len"] == 2000


async def test_multipart_over_its_limit_rejected():
    headers = {"Content-Type": "multipart/form-data; boundary=abc"}
    async with _client(_make_app()) as c:
        r = await c.post("/echo", content=b"x" * 5000, headers=headers)
    assert r.status_code == 413
    assert r.json()["max_bytes"] == MULTIPART_LIMIT


async def test_route_override_raises_limit():
    # /big-upload is overridden to 8 KB, so a 5 KB JSON body is accepted there
    # even though the global JSON limit is 1 KB.
    app = _make_app(route_overrides={"/big-upload": 8000})
    async with _client(app) as c:
        ok = await c.post("/big-upload", content=b"x" * 5000, headers={"Content-Type": "application/json"})
        # The same body is still rejected on a non-overridden route.
        blocked = await c.post("/echo", content=b"x" * 5000, headers={"Content-Type": "application/json"})
    assert ok.status_code == 200
    assert ok.json()["len"] == 5000
    assert blocked.status_code == 413


async def test_route_override_lowers_limit():
    app = _make_app(route_overrides={"/tiny": 100})
    async with _client(app) as c:
        r = await c.post("/tiny", content=b"x" * 500, headers={"Content-Type": "application/json"})
    assert r.status_code == 413
    assert r.json()["max_bytes"] == 100


async def test_global_registry_override():
    clear_route_body_limits()
    set_route_body_limit("/tiny", 50)
    try:
        async with _client(_make_app()) as c:
            r = await c.post("/tiny", content=b"x" * 200, headers={"Content-Type": "application/json"})
        assert r.status_code == 413
        assert r.json()["max_bytes"] == 50
    finally:
        clear_route_body_limits()


async def test_streaming_body_rejected_without_content_length():
    # An async stream produces a chunked request with no Content-Length, forcing
    # the streaming guard (rather than the fast path) to trip.
    async def gen():
        for _ in range(5):
            yield b"x" * 400  # 2000 bytes total > 1 KB JSON limit

    async with _client(_make_app()) as c:
        r = await c.post("/echo", content=gen(), headers={"Content-Type": "application/json"})
    assert r.status_code == 413
    assert r.json()["max_bytes"] == JSON_LIMIT


async def test_streaming_body_within_limit_allowed():
    async def gen():
        yield b"x" * 300
        yield b"x" * 300

    async with _client(_make_app()) as c:
        r = await c.post("/echo", content=gen(), headers={"Content-Type": "application/json"})
    assert r.status_code == 200
    assert r.json()["len"] == 600


async def test_disabled_middleware_allows_large_body():
    async with _client(_make_app(enabled=False)) as c:
        r = await c.post("/echo", content=b"x" * 50000, headers={"Content-Type": "application/json"})
    assert r.status_code == 200
    assert r.json()["len"] == 50000


async def test_request_without_body_passes():
    async with _client(_make_app()) as c:
        r = await c.post("/echo")
    assert r.status_code == 200
    assert r.json()["len"] == 0
