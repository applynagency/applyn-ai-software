"""Tests for unified ingest targets and health board."""

import pytest

from app.services.integration_poll_sources import list_ingest_targets
from app.tests.conftest import auth_headers, create_authenticated_user

H = auth_headers


@pytest.mark.asyncio
async def test_health_board_endpoint(client):
    _, t = await create_authenticated_user(client, email="hb1@e.com", username="hb1")
    token = t["access_token"]
    await client.post(
        "/v1/integrations/connect", headers=H(token),
        json={"integration_key": "SLACK", "credentials": {"bot_token": "xoxb-test"}},
    )
    board = (await client.get("/v1/integrations/connections/health-board", headers=H(token))).json()
    assert isinstance(board, list)
    assert len(board) >= 1
    assert board[0]["integration_key"] == "SLACK"
    assert "live_data" in board[0]
    assert "alerts_24h" in board[0]


@pytest.mark.asyncio
async def test_ingest_targets_from_integration_connection(client):
    from app.database.session import AsyncSessionLocal
    from app.core.security import decode_token

    _, t = await create_authenticated_user(client, email="hb2@e.com", username="hb2")
    token = t["access_token"]
    org_id = decode_token(token)["organization_id"]
    conn = (await client.post(
        "/v1/integrations/connect", headers=H(token),
        json={"integration_key": "PROMETHEUS", "credentials": {"endpoint": "http://prom.example"}},
    )).json()

    async with AsyncSessionLocal() as session:
        targets = await list_ingest_targets(session, org_id, {"PROMETHEUS"})
        assert any(t.provider == "PROMETHEUS" for t in targets)
        assert conn["id"]  # connection created
