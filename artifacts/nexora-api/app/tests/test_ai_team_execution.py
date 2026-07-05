"""Tests for Sprint 37B — single Team Agent execution."""

from app.tests.conftest import auth_headers, create_authenticated_user


async def _team_and_agent(client, token, *, agent_name="Backend Engineer"):
    team = (
        await client.post(
            "/v1/ai-teams",
            headers=auth_headers(token),
            json={"name": "Acme Engineering Team"},
        )
    ).json()
    agent = (
        await client.post(
            "/v1/ai-team-agents",
            headers=auth_headers(token),
            json={
                "team_id": team["id"],
                "name": agent_name,
                "role": "Engineering",
                "instructions": "You are a senior backend engineer.",
                "model": "claude-sonnet",
                "temperature": 0.3,
                "max_tokens": 1024,
            },
        )
    ).json()
    return team, agent


async def test_execute_agent_offline(client):
    _, tokens = await create_authenticated_user(
        client, email="exec1@example.com", username="exec1user"
    )
    token = tokens["access_token"]
    _, agent = await _team_and_agent(client, token)

    response = await client.post(
        f"/v1/ai-team-agents/{agent['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "Review this API architecture"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["agent_id"] == agent["id"]
    assert body["agent_name"] == agent["name"]
    assert body["status"] == "COMPLETED"
    assert body["response"]  # deterministic offline response is non-empty
    assert "Review this API architecture" in body["response"]
    assert isinstance(body["execution_time_ms"], int)
    assert body["run_id"]


async def test_execution_persisted_and_history_visible(client):
    _, tokens = await create_authenticated_user(
        client, email="exec2@example.com", username="exec2user"
    )
    token = tokens["access_token"]
    _, agent = await _team_and_agent(client, token)

    await client.post(
        f"/v1/ai-team-agents/{agent['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "First prompt"},
    )
    await client.post(
        f"/v1/ai-team-agents/{agent['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "Second prompt"},
    )

    history = await client.get(
        f"/v1/ai-team-agents/{agent['id']}/runs", headers=auth_headers(token)
    )
    assert history.status_code == 200
    body = history.json()
    assert body["total"] == 2
    prompts = {item["prompt"] for item in body["items"]}
    assert prompts == {"First prompt", "Second prompt"}
    assert all(item["status"] == "COMPLETED" for item in body["items"])
    # Most recent first.
    assert body["items"][0]["prompt"] == "Second prompt"


async def test_empty_prompt_rejected(client):
    _, tokens = await create_authenticated_user(
        client, email="exec3@example.com", username="exec3user"
    )
    token = tokens["access_token"]
    _, agent = await _team_and_agent(client, token)
    response = await client.post(
        f"/v1/ai-team-agents/{agent['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": ""},
    )
    assert response.status_code == 422


async def test_execution_tenant_isolation(client):
    _, tokens_a = await create_authenticated_user(
        client, email="exec-a@example.com", username="execaa"
    )
    _, tokens_b = await create_authenticated_user(
        client, email="exec-b@example.com", username="execbb"
    )
    _, agent_a = await _team_and_agent(client, tokens_a["access_token"])

    # Org B cannot execute Org A's agent.
    run = await client.post(
        f"/v1/ai-team-agents/{agent_a['id']}/execute",
        headers=auth_headers(tokens_b["access_token"]),
        json={"prompt": "intrusion attempt"},
    )
    assert run.status_code == 404

    # Org B cannot view Org A's agent run history.
    hist = await client.get(
        f"/v1/ai-team-agents/{agent_a['id']}/runs",
        headers=auth_headers(tokens_b["access_token"]),
    )
    assert hist.status_code == 404


async def test_audit_event_on_execution(client):
    from sqlalchemy import select

    from app.database.session import AsyncSessionLocal
    from app.models.audit import AuditLog

    _, tokens = await create_authenticated_user(
        client, email="exec-audit@example.com", username="execaudit"
    )
    token = tokens["access_token"]
    _, agent = await _team_and_agent(client, token)
    resp = await client.post(
        f"/v1/ai-team-agents/{agent['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "audit me"},
    )
    run_id = resp.json()["run_id"]

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(AuditLog).where(AuditLog.action == "ai_agent_executed")
            )
        ).scalars().all()
    assert any(
        r.resource_id == agent["id"] and (r.details or {}).get("run_id") == run_id
        for r in rows
    )


async def test_execution_failure_persists_failed_run(client, monkeypatch):
    from sqlalchemy import select

    from app.core.exceptions import AgentError
    from app.database.session import AsyncSessionLocal
    from app.models.ai_team import AITeamAgentRun

    _, tokens = await create_authenticated_user(
        client, email="exec-fail@example.com", username="execfail"
    )
    token = tokens["access_token"]
    _, agent = await _team_and_agent(client, token)

    async def boom(self, **kwargs):
        raise AgentError("simulated provider outage")

    monkeypatch.setattr("app.services.ai_team_runner.AITeamAgentRunner.run", boom)

    response = await client.post(
        f"/v1/ai-team-agents/{agent['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "this will fail"},
    )
    assert response.status_code == 502
    # The internal LLM error must not leak to the customer.
    assert "simulated provider outage" not in response.text

    async with AsyncSessionLocal() as session:
        runs = (
            await session.execute(
                select(AITeamAgentRun).where(AITeamAgentRun.agent_id == agent["id"])
            )
        ).scalars().all()
    assert len(runs) == 1
    assert runs[0].status == "FAILED"
    assert runs[0].response is None
