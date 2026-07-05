"""Tests for Sprint 37A — Custom AI Teams (Customer AI Workforce)."""

from app.tests.conftest import auth_headers, create_authenticated_user


async def _create_team(client, token, *, name="Acme Engineering Team", description="Builds the product"):
    response = await client.post(
        "/v1/ai-teams",
        headers=auth_headers(token),
        json={"name": name, "description": description},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_agent(client, token, team_id, *, name="Backend Engineer", role="Engineering"):
    response = await client.post(
        "/v1/ai-team-agents",
        headers=auth_headers(token),
        json={
            "team_id": team_id,
            "name": name,
            "role": role,
            "instructions": "You are a senior backend engineer.",
            "model": "claude-sonnet",
            "temperature": 0.4,
            "max_tokens": 2048,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


# --------------------------------------------------------------------- teams
async def test_create_team(client):
    _, tokens = await create_authenticated_user(
        client, email="team-create@example.com", username="teamcreate"
    )
    team = await _create_team(client, tokens["access_token"])
    assert team["name"] == "Acme Engineering Team"
    assert team["status"] == "ACTIVE"
    assert team["organization_id"]
    assert team["agent_count"] == 0
    assert team["agents"] == []


async def test_list_teams(client):
    _, tokens = await create_authenticated_user(
        client, email="team-list@example.com", username="teamlist"
    )
    await _create_team(client, tokens["access_token"], name="Marketing Team")
    response = await client.get("/v1/ai-teams", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert any(t["name"] == "Marketing Team" for t in body["items"])


async def test_update_team(client):
    _, tokens = await create_authenticated_user(
        client, email="team-update@example.com", username="teamupdate"
    )
    team = await _create_team(client, tokens["access_token"])
    response = await client.put(
        f"/v1/ai-teams/{team['id']}",
        headers=auth_headers(tokens["access_token"]),
        json={"name": "Renamed Team", "status": "INACTIVE"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "Renamed Team"
    assert body["status"] == "INACTIVE"


async def test_delete_team(client):
    _, tokens = await create_authenticated_user(
        client, email="team-delete@example.com", username="teamdelete"
    )
    team = await _create_team(client, tokens["access_token"])
    response = await client.delete(
        f"/v1/ai-teams/{team['id']}", headers=auth_headers(tokens["access_token"])
    )
    assert response.status_code == 204
    missing = await client.get(
        f"/v1/ai-teams/{team['id']}", headers=auth_headers(tokens["access_token"])
    )
    assert missing.status_code == 404


# -------------------------------------------------------------------- agents
async def test_create_and_list_agents(client):
    _, tokens = await create_authenticated_user(
        client, email="agent-create@example.com", username="aiteamagentc"
    )
    token = tokens["access_token"]
    team = await _create_team(client, token)
    agent = await _create_agent(client, token, team["id"])
    assert agent["team_id"] == team["id"]
    assert agent["role"] == "Engineering"
    assert agent["model"] == "claude-sonnet"
    assert agent["is_active"] is True

    # Team detail embeds the agent.
    detail = await client.get(f"/v1/ai-teams/{team['id']}", headers=auth_headers(token))
    assert detail.json()["agent_count"] == 1

    # Flat listing filtered by team.
    listing = await client.get(
        f"/v1/ai-team-agents?team_id={team['id']}", headers=auth_headers(token)
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1


async def test_update_agent(client):
    _, tokens = await create_authenticated_user(
        client, email="agent-update@example.com", username="aiteamagentu"
    )
    token = tokens["access_token"]
    team = await _create_team(client, token)
    agent = await _create_agent(client, token, team["id"])
    response = await client.put(
        f"/v1/ai-team-agents/{agent['id']}",
        headers=auth_headers(token),
        json={"name": "Lead Backend Engineer", "temperature": 1.1},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "Lead Backend Engineer"
    assert body["temperature"] == 1.1


async def test_disable_agent(client):
    _, tokens = await create_authenticated_user(
        client, email="agent-disable@example.com", username="aiteamagentd"
    )
    token = tokens["access_token"]
    team = await _create_team(client, token)
    agent = await _create_agent(client, token, team["id"])
    response = await client.put(
        f"/v1/ai-team-agents/{agent['id']}",
        headers=auth_headers(token),
        json={"is_active": False},
    )
    assert response.status_code == 200, response.text
    assert response.json()["is_active"] is False


async def test_delete_agent(client):
    _, tokens = await create_authenticated_user(
        client, email="agent-del@example.com", username="aiteamagentx"
    )
    token = tokens["access_token"]
    team = await _create_team(client, token)
    agent = await _create_agent(client, token, team["id"])
    response = await client.delete(
        f"/v1/ai-team-agents/{agent['id']}", headers=auth_headers(token)
    )
    assert response.status_code == 204
    missing = await client.get(
        f"/v1/ai-team-agents/{agent['id']}", headers=auth_headers(token)
    )
    assert missing.status_code == 404


# --------------------------------------------------------- input validation
async def test_invalid_temperature_rejected(client):
    _, tokens = await create_authenticated_user(
        client, email="agent-bad@example.com", username="aiteamagentv"
    )
    token = tokens["access_token"]
    team = await _create_team(client, token)
    response = await client.post(
        "/v1/ai-team-agents",
        headers=auth_headers(token),
        json={"team_id": team["id"], "name": "X", "role": "Engineering", "temperature": 5},
    )
    assert response.status_code == 422


async def test_create_team_requires_name(client):
    _, tokens = await create_authenticated_user(
        client, email="team-noname@example.com", username="teamnoname"
    )
    response = await client.post(
        "/v1/ai-teams",
        headers=auth_headers(tokens["access_token"]),
        json={"description": "no name"},
    )
    assert response.status_code == 422


# ------------------------------------------------------------ tenant isolation
async def test_team_isolation_between_organizations(client):
    _, tokens_a = await create_authenticated_user(
        client, email="tenant-a@example.com", username="tenanta"
    )
    _, tokens_b = await create_authenticated_user(
        client, email="tenant-b@example.com", username="tenantb"
    )
    team_a = await _create_team(client, tokens_a["access_token"], name="Org A Team")

    # Org B cannot read Org A's team.
    response = await client.get(
        f"/v1/ai-teams/{team_a['id']}", headers=auth_headers(tokens_b["access_token"])
    )
    assert response.status_code == 404

    # Org B cannot update/delete it either.
    upd = await client.put(
        f"/v1/ai-teams/{team_a['id']}",
        headers=auth_headers(tokens_b["access_token"]),
        json={"name": "hijacked"},
    )
    assert upd.status_code == 404
    dele = await client.delete(
        f"/v1/ai-teams/{team_a['id']}", headers=auth_headers(tokens_b["access_token"])
    )
    assert dele.status_code == 404

    # Org B's listing does not include Org A's team.
    listing = await client.get("/v1/ai-teams", headers=auth_headers(tokens_b["access_token"]))
    assert all(t["id"] != team_a["id"] for t in listing.json()["items"])


async def test_agent_cross_org_attachment_blocked(client):
    _, tokens_a = await create_authenticated_user(
        client, email="tenant-c@example.com", username="tenantc"
    )
    _, tokens_b = await create_authenticated_user(
        client, email="tenant-d@example.com", username="tenantd"
    )
    team_a = await _create_team(client, tokens_a["access_token"], name="Org C Team")

    # Org B cannot attach an agent to Org A's team.
    response = await client.post(
        "/v1/ai-team-agents",
        headers=auth_headers(tokens_b["access_token"]),
        json={"team_id": team_a["id"], "name": "Intruder", "role": "Engineering"},
    )
    assert response.status_code == 404


# --------------------------------------------------------------- audit events
async def test_audit_events_recorded(client):
    from sqlalchemy import select

    from app.database.session import AsyncSessionLocal
    from app.models.audit import AuditLog

    _, tokens = await create_authenticated_user(
        client, email="audit@example.com", username="audituser"
    )
    token = tokens["access_token"]
    team = await _create_team(client, token)
    agent = await _create_agent(client, token, team["id"])
    await client.put(
        f"/v1/ai-teams/{team['id']}",
        headers=auth_headers(token),
        json={"name": "Audited Team"},
    )
    await client.delete(f"/v1/ai-team-agents/{agent['id']}", headers=auth_headers(token))

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(AuditLog).where(AuditLog.resource_type.in_(["ai_team", "ai_team_agent"]))
            )
        ).scalars().all()

    actions = {row.action for row in rows}
    assert "ai_team_created" in actions
    assert "ai_team_updated" in actions
    assert "ai_agent_created" in actions
    assert "ai_agent_deleted" in actions

    # No secrets and proper linkage in details.
    team_created = next(r for r in rows if r.action == "ai_team_created")
    assert team_created.details.get("team_id") == team["id"]
