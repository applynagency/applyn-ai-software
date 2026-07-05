"""Tests for Sprint 40A — Incident Investigation Engine."""

from app.services.tool_registry import PROVIDER_ACTIONS
from app.tests.conftest import auth_headers, create_authenticated_user


async def _team_agent(client, token, name="Ops"):
    team = (
        await client.post("/v1/ai-teams", headers=auth_headers(token), json={"name": name})
    ).json()
    agent = (
        await client.post(
            "/v1/ai-team-agents",
            headers=auth_headers(token),
            json={
                "team_id": team["id"],
                "name": "SRE",
                "role": "Operations",
                "instructions": "Investigate production incidents.",
                "model": "claude-sonnet",
                "temperature": 0.2,
                "max_tokens": 300,
                "is_active": True,
            },
        )
    ).json()
    return team, agent


async def _tool(client, token, provider, name=None):
    return (
        await client.post(
            "/v1/ai-tools",
            headers=auth_headers(token),
            json={"provider": provider, "name": name or f"{provider} tool"},
        )
    ).json()


async def _assign(client, token, agent_id, tool_id):
    resp = await client.post(
        f"/v1/ai-team-agents/{agent_id}/tools",
        headers=auth_headers(token),
        json={"tool_id": tool_id},
    )
    assert resp.status_code in (200, 201), resp.text


async def test_single_tool_investigation(client):
    _, tokens = await create_authenticated_user(client, email="i1@example.com", username="inc1")
    token = tokens["access_token"]
    team, agent = await _team_agent(client, token)
    tool = await _tool(client, token, "KUBERNETES", "Prod Cluster")
    await _assign(client, token, agent["id"], tool["id"])

    resp = await client.post(
        "/v1/incidents/investigate",
        headers=auth_headers(token),
        json={"team_id": team["id"], "prompt": "Why is the production API returning 500 errors?"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["agent_id"] == agent["id"]
    assert len(body["steps"]) >= 1
    assert all(s["tool_provider"] == "KUBERNETES" for s in body["steps"])
    # Every executed action is a known read-only action.
    assert all(s["action"] in PROVIDER_ACTIONS["KUBERNETES"] for s in body["steps"])
    assert body["root_cause"]
    assert body["recommendations"]
    assert body["findings"]


async def test_multi_tool_investigation(client):
    _, tokens = await create_authenticated_user(client, email="i2@example.com", username="inc2")
    token = tokens["access_token"]
    team, agent = await _team_agent(client, token)
    for provider in ("KUBERNETES", "PROMETHEUS", "GITHUB"):
        tool = await _tool(client, token, provider)
        await _assign(client, token, agent["id"], tool["id"])

    resp = await client.post(
        "/v1/incidents/investigate",
        headers=auth_headers(token),
        json={
            "team_id": team["id"],
            "prompt": "Investigate elevated error rate after the latest release.",
            "context": {"owner": "acme", "repo": "api"},
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    providers = {s["tool_provider"] for s in body["steps"]}
    assert {"KUBERNETES", "PROMETHEUS", "GITHUB"}.issubset(providers)
    # Steps are ordered.
    orders = [s["step_order"] for s in body["steps"]]
    assert orders == sorted(orders)


async def test_timeline_generation(client):
    _, tokens = await create_authenticated_user(client, email="i3@example.com", username="inc3")
    token = tokens["access_token"]
    team, agent = await _team_agent(client, token)
    tool = await _tool(client, token, "DATADOG")
    await _assign(client, token, agent["id"], tool["id"])
    inv = (
        await client.post(
            "/v1/incidents/investigate",
            headers=auth_headers(token),
            json={"team_id": team["id"], "prompt": "Latency spike investigation."},
        )
    ).json()

    tl = await client.get(
        f"/v1/incidents/{inv['id']}/timeline", headers=auth_headers(token)
    )
    assert tl.status_code == 200
    data = tl.json()
    assert data["investigation_id"] == inv["id"]
    assert data["status"] == "COMPLETED"
    assert len(data["steps"]) >= 1
    assert [s["step_order"] for s in data["steps"]] == sorted(s["step_order"] for s in data["steps"])


async def test_rca_and_history_persistence(client):
    _, tokens = await create_authenticated_user(client, email="i4@example.com", username="inc4")
    token = tokens["access_token"]
    team, agent = await _team_agent(client, token)
    tool = await _tool(client, token, "KUBERNETES")
    await _assign(client, token, agent["id"], tool["id"])
    inv = (
        await client.post(
            "/v1/incidents/investigate",
            headers=auth_headers(token),
            json={"team_id": team["id"], "prompt": "Pods crash looping in prod."},
        )
    ).json()

    # Listed in history.
    listing = await client.get("/v1/incidents", headers=auth_headers(token))
    assert listing.status_code == 200
    assert any(i["id"] == inv["id"] for i in listing.json()["items"])

    # Detail persisted with RCA + steps + findings.
    detail = await client.get(f"/v1/incidents/{inv['id']}", headers=auth_headers(token))
    assert detail.status_code == 200
    d = detail.json()
    assert d["summary"] and d["root_cause"] and d["recommendations"]
    assert len(d["steps"]) >= 1
    assert len(d["findings"]) == len(d["steps"])


async def test_investigation_without_tools_is_graceful(client):
    _, tokens = await create_authenticated_user(client, email="i5@example.com", username="inc5")
    token = tokens["access_token"]
    team, _agent = await _team_agent(client, token)
    resp = await client.post(
        "/v1/incidents/investigate",
        headers=auth_headers(token),
        json={"team_id": team["id"], "prompt": "Something is wrong."},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["steps"] == []
    assert "connect" in body["recommendations"].lower()


async def test_tenant_isolation(client):
    _, tokens_a = await create_authenticated_user(client, email="ia@example.com", username="incaa")
    _, tokens_b = await create_authenticated_user(client, email="ib@example.com", username="incbb")
    token_a = tokens_a["access_token"]
    token_b = tokens_b["access_token"]
    team_a, agent_a = await _team_agent(client, token_a)
    tool = await _tool(client, token_a, "KUBERNETES")
    await _assign(client, token_a, agent_a["id"], tool["id"])
    inv = (
        await client.post(
            "/v1/incidents/investigate",
            headers=auth_headers(token_a),
            json={"team_id": team_a["id"], "prompt": "Org A incident."},
        )
    ).json()

    # Org B cannot read org A's investigation or timeline.
    assert (
        await client.get(f"/v1/incidents/{inv['id']}", headers=auth_headers(token_b))
    ).status_code == 404
    assert (
        await client.get(f"/v1/incidents/{inv['id']}/timeline", headers=auth_headers(token_b))
    ).status_code == 404
    # Org B cannot investigate using org A's team.
    assert (
        await client.post(
            "/v1/incidents/investigate",
            headers=auth_headers(token_b),
            json={"team_id": team_a["id"], "prompt": "x"},
        )
    ).status_code == 404
    # Org B's history does not include org A's investigation.
    listing_b = await client.get("/v1/incidents", headers=auth_headers(token_b))
    assert all(i["id"] != inv["id"] for i in listing_b.json()["items"])


async def test_audit_logging(client):
    from sqlalchemy import select

    from app.database.session import AsyncSessionLocal
    from app.models.audit import AuditLog

    _, tokens = await create_authenticated_user(client, email="i6@example.com", username="inc6")
    token = tokens["access_token"]
    team, agent = await _team_agent(client, token)
    tool = await _tool(client, token, "KUBERNETES")
    await _assign(client, token, agent["id"], tool["id"])
    await client.post(
        "/v1/incidents/investigate",
        headers=auth_headers(token),
        json={"team_id": team["id"], "prompt": "Audit check."},
    )

    async with AsyncSessionLocal() as session:
        actions = {r.action for r in (await session.execute(select(AuditLog))).scalars().all()}
    assert "incident_investigation_started" in actions
    assert "incident_investigation_completed" in actions
    assert "tool_executed" in actions
