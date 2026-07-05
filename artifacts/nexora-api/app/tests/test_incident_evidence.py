"""Tests for incident operational evidence endpoint."""

import pytest

from app.tests.conftest import auth_headers, create_authenticated_user

H = auth_headers


@pytest.mark.asyncio
async def test_incident_evidence_endpoint(client):
    _, tokens = await create_authenticated_user(client, email="ev1@example.com", username="ev1")
    token = tokens["access_token"]
    team = (await client.post("/v1/ai-teams", headers=H(token), json={"name": "SRE"})).json()
    agent = (
        await client.post(
            "/v1/ai-team-agents",
            headers=H(token),
            json={
                "team_id": team["id"],
                "name": "Agent",
                "role": "SRE",
                "instructions": "Investigate.",
                "model": "claude-sonnet",
                "temperature": 0.2,
                "max_tokens": 300,
                "is_active": True,
            },
        )
    ).json()
    for provider in ("GITHUB", "KUBERNETES", "PROMETHEUS", "DATADOG"):
        tool = (
            await client.post(
                "/v1/ai-tools", headers=H(token), json={"provider": provider, "name": f"{provider} t"},
            )
        ).json()
        await client.post(
            f"/v1/ai-team-agents/{agent['id']}/tools",
            headers=H(token),
            json={"tool_id": tool["id"]},
        )
    inv = (
        await client.post(
            "/v1/incidents/investigate",
            headers=H(token),
            json={"team_id": team["id"], "prompt": "API errors after deploy."},
        )
    ).json()
    resp = await client.get(f"/v1/incidents/{inv['id']}/evidence", headers=H(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["investigation_id"] == inv["id"]
    assert "logs" in body
    assert "metrics" in body
    assert "build_context" in body
