"""Tests for Sprint 39A — Agent Memory System."""

from app.tests.conftest import auth_headers, create_authenticated_user


async def _agent(client, token, name="CTO", role="Leadership"):
    team = (
        await client.post("/v1/ai-teams", headers=auth_headers(token), json={"name": "Eng Team"})
    ).json()
    agent = (
        await client.post(
            "/v1/ai-team-agents",
            headers=auth_headers(token),
            json={
                "team_id": team["id"],
                "name": name,
                "role": role,
                "instructions": f"You are the {name}. Be concise.",
                "model": "claude-sonnet",
                "temperature": 0.2,
                "max_tokens": 300,
                "is_active": True,
            },
        )
    ).json()
    return team, agent


async def test_memory_crud(client):
    _, tokens = await create_authenticated_user(client, email="m1@example.com", username="mem1")
    token = tokens["access_token"]
    _, agent = await _agent(client, token)

    created = await client.post(
        f"/v1/ai-team-agents/{agent['id']}/memory",
        headers=auth_headers(token),
        json={
            "memory_type": "MEMORY_DECISION",
            "title": "PostgreSQL selected as primary DB",
            "content": "We chose PostgreSQL for the platform's primary database.",
            "importance_score": 9,
        },
    )
    assert created.status_code == 201, created.text
    mem = created.json()
    assert mem["title"] == "PostgreSQL selected as primary DB"
    assert mem["importance_score"] == 9

    listed = await client.get(
        f"/v1/ai-team-agents/{agent['id']}/memory", headers=auth_headers(token)
    )
    assert listed.json()["total"] == 1

    updated = await client.put(
        f"/v1/ai-team-agents/memory/{mem['id']}",
        headers=auth_headers(token),
        json={"importance_score": 10, "content": "PostgreSQL is the primary database. Final."},
    )
    assert updated.status_code == 200
    assert updated.json()["importance_score"] == 10

    deleted = await client.delete(
        f"/v1/ai-team-agents/memory/{mem['id']}", headers=auth_headers(token)
    )
    assert deleted.status_code == 204
    again = await client.get(
        f"/v1/ai-team-agents/{agent['id']}/memory", headers=auth_headers(token)
    )
    assert again.json()["total"] == 0


async def test_invalid_memory_type_rejected(client):
    _, tokens = await create_authenticated_user(client, email="m2@example.com", username="mem2")
    token = tokens["access_token"]
    _, agent = await _agent(client, token)
    resp = await client.post(
        f"/v1/ai-team-agents/{agent['id']}/memory",
        headers=auth_headers(token),
        json={"memory_type": "NONSENSE", "title": "x", "content": "y"},
    )
    assert resp.status_code == 422


async def test_filter_and_search_memory(client):
    _, tokens = await create_authenticated_user(client, email="m3@example.com", username="mem3")
    token = tokens["access_token"]
    _, agent = await _agent(client, token)
    for mt, title, content in [
        ("MEMORY_DECISION", "PostgreSQL selected", "Use PostgreSQL primary db"),
        ("MEMORY_LESSON", "Cache stampede lesson", "Add jitter to Redis TTLs"),
        ("MEMORY_DECISION", "Microservices approved", "Split into services"),
    ]:
        await client.post(
            f"/v1/ai-team-agents/{agent['id']}/memory",
            headers=auth_headers(token),
            json={"memory_type": mt, "title": title, "content": content, "importance_score": 5},
        )
    only_decisions = await client.get(
        f"/v1/ai-team-agents/{agent['id']}/memory?memory_type=MEMORY_DECISION",
        headers=auth_headers(token),
    )
    assert only_decisions.json()["total"] == 2
    searched = await client.get(
        f"/v1/ai-team-agents/{agent['id']}/memory?search=Redis",
        headers=auth_headers(token),
    )
    assert searched.json()["total"] == 1
    assert searched.json()["items"][0]["title"] == "Cache stampede lesson"


async def test_execution_uses_relevant_memory(client):
    """Success criteria: a saved decision is recalled on a later, related run."""
    _, tokens = await create_authenticated_user(client, email="m4@example.com", username="mem4")
    token = tokens["access_token"]
    _, agent = await _agent(client, token)
    # Day 1: save a decision.
    await client.post(
        f"/v1/ai-team-agents/{agent['id']}/memory",
        headers=auth_headers(token),
        json={
            "memory_type": "MEMORY_DECISION",
            "title": "PostgreSQL selected as primary database",
            "content": "PostgreSQL was selected as the primary database for the platform.",
            "importance_score": 9,
        },
    )
    # Day 30: a related request — memory should be recalled.
    resp = await client.post(
        f"/v1/ai-team-agents/{agent['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "Design an analytics service and choose the database"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "PostgreSQL selected as primary database" in body["memory_sources"]


async def test_execution_without_memory_has_empty_sources(client):
    _, tokens = await create_authenticated_user(client, email="m5@example.com", username="mem5")
    token = tokens["access_token"]
    _, agent = await _agent(client, token)
    resp = await client.post(
        f"/v1/ai-team-agents/{agent['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "Anything"},
    )
    assert resp.json()["memory_sources"] == []


async def test_relevance_ranking(client):
    """The most semantically relevant memory ranks first in sources."""
    _, tokens = await create_authenticated_user(client, email="m6@example.com", username="mem6")
    token = tokens["access_token"]
    _, agent = await _agent(client, token)
    memories = [
        ("MEMORY_DECISION", "Kubernetes orchestration adopted", "We run on Kubernetes clusters"),
        ("MEMORY_DECISION", "PostgreSQL database selected", "PostgreSQL is the primary database engine"),
        ("MEMORY_LESSON", "Marketing copy tone", "Keep marketing copy friendly"),
    ]
    for mt, title, content in memories:
        await client.post(
            f"/v1/ai-team-agents/{agent['id']}/memory",
            headers=auth_headers(token),
            json={"memory_type": mt, "title": title, "content": content, "importance_score": 5},
        )
    resp = await client.post(
        f"/v1/ai-team-agents/{agent['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "Which database engine should the new PostgreSQL service use?"},
    )
    sources = resp.json()["memory_sources"]
    assert sources, "expected at least one memory source"
    assert sources[0] == "PostgreSQL database selected"


async def test_team_execution_reports_memory_sources(client):
    _, tokens = await create_authenticated_user(client, email="m7@example.com", username="mem7")
    token = tokens["access_token"]
    team, agent = await _agent(client, token)
    await client.post(
        f"/v1/ai-team-agents/{agent['id']}/memory",
        headers=auth_headers(token),
        json={
            "memory_type": "MEMORY_DECISION",
            "title": "Microservices architecture approved",
            "content": "The team approved a microservices architecture.",
            "importance_score": 8,
        },
    )
    resp = await client.post(
        f"/v1/ai-teams/{team['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "Plan the microservices architecture rollout"},
    )
    assert resp.status_code == 200, resp.text
    assert "Microservices architecture approved" in resp.json()["memory_sources"]


async def test_memory_tenant_isolation(client):
    _, tokens_a = await create_authenticated_user(client, email="ma@example.com", username="maa")
    _, tokens_b = await create_authenticated_user(client, email="mb@example.com", username="mbb")
    token_a = tokens_a["access_token"]
    token_b = tokens_b["access_token"]
    _, agent = await _agent(client, token_a)
    mem = (
        await client.post(
            f"/v1/ai-team-agents/{agent['id']}/memory",
            headers=auth_headers(token_a),
            json={"memory_type": "MEMORY_DECISION", "title": "Secret", "content": "x"},
        )
    ).json()

    # Cross-org cannot list the agent's memory, nor edit/delete it.
    assert (
        await client.get(
            f"/v1/ai-team-agents/{agent['id']}/memory", headers=auth_headers(token_b)
        )
    ).status_code == 404
    assert (
        await client.put(
            f"/v1/ai-team-agents/memory/{mem['id']}",
            headers=auth_headers(token_b),
            json={"title": "hacked"},
        )
    ).status_code == 404
    assert (
        await client.delete(
            f"/v1/ai-team-agents/memory/{mem['id']}", headers=auth_headers(token_b)
        )
    ).status_code == 404


async def test_memory_audit_events(client):
    from sqlalchemy import select

    from app.database.session import AsyncSessionLocal
    from app.models.audit import AuditLog

    _, tokens = await create_authenticated_user(client, email="m8@example.com", username="mem8")
    token = tokens["access_token"]
    _, agent = await _agent(client, token)
    mem = (
        await client.post(
            f"/v1/ai-team-agents/{agent['id']}/memory",
            headers=auth_headers(token),
            json={
                "memory_type": "MEMORY_DECISION",
                "title": "PostgreSQL selected",
                "content": "Use PostgreSQL as primary database",
                "importance_score": 9,
            },
        )
    ).json()
    await client.put(
        f"/v1/ai-team-agents/memory/{mem['id']}",
        headers=auth_headers(token),
        json={"importance_score": 10},
    )
    # An execution that recalls memory should log ai_memory_used.
    await client.post(
        f"/v1/ai-team-agents/{agent['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "What database should we use for PostgreSQL workloads?"},
    )
    await client.delete(
        f"/v1/ai-team-agents/memory/{mem['id']}", headers=auth_headers(token)
    )

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(select(AuditLog))).scalars().all()
    actions = {r.action for r in rows}
    assert "ai_memory_created" in actions
    assert "ai_memory_updated" in actions
    assert "ai_memory_used" in actions
    assert "ai_memory_deleted" in actions
