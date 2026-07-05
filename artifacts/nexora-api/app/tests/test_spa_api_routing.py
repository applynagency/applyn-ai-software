"""SPA vs API routing — ensure API paths return JSON, not the HTML shell."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import BASE_PATH, app


@pytest_asyncio.fixture
async def root_client(setup_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_nexora_api_health_returns_json(root_client: AsyncClient) -> None:
    resp = await root_client.get(f"{BASE_PATH}/health")
    assert resp.status_code == 200
    assert "application/json" in resp.headers.get("content-type", "")
    body = resp.json()
    assert body.get("status") == "healthy"


@pytest.mark.asyncio
async def test_root_health_redirects_to_api_health(root_client: AsyncClient) -> None:
    resp = await root_client.get("/health", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"].endswith(f"{BASE_PATH}/health")


@pytest.mark.asyncio
async def test_bare_v1_path_returns_json_not_spa_html(root_client: AsyncClient) -> None:
    resp = await root_client.get("/v1/pilot/readiness")
    assert resp.status_code == 404
    assert "application/json" in resp.headers.get("content-type", "")
    detail = resp.json().get("detail", "")
    assert "nexora-api" in detail.lower() or BASE_PATH in detail
    assert "<html" not in resp.text.lower()


@pytest.mark.asyncio
async def test_unknown_spa_route_still_serves_index_html(root_client: AsyncClient) -> None:
    resp = await root_client.get("/pilot/execution")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "app.js" in resp.text or "__ASSETS__" in resp.text or "id=\"app\"" in resp.text


@pytest.mark.asyncio
async def test_pilot_operator_chunk_is_served_as_javascript(root_client: AsyncClient) -> None:
    resp = await root_client.get("/pilot-operator.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers.get("content-type", "").lower()
    assert "function renderPilotExecution" in resp.text
