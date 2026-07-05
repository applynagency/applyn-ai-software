"""Tests for Sprint 37C — orchestrated multi-agent team collaboration."""

from app.tests.conftest import auth_headers, create_authenticated_user


async def _make_team(client, token, name="Engineering Team"):
    return (
        await client.post(
            "/v1/ai-teams",
            headers=auth_headers(token),
            json={"name": name},
        )
    ).json()


async def _add_agent(client, token, team_id, name, role="Engineering", active=True):
    return (
        await client.post(
            "/v1/ai-team-agents",
            headers=auth_headers(token),
            json={
                "team_id": team_id,
                "name": name,
                "role": role,
                "instructions": f"You are the {name}.",
                "model": "claude-sonnet",
                "temperature": 0.3,
                "max_tokens": 512,
                "is_active": active,
            },
        )
    ).json()


async def _engineering_team(client, token):
    team = await _make_team(client, token)
    # Intentionally created out of collaboration order to exercise ordering.
    await _add_agent(client, token, team["id"], "QA Engineer", role="Quality")
    await _add_agent(client, token, team["id"], "Backend Engineer", role="Engineering")
    await _add_agent(client, token, team["id"], "CTO", role="Leadership")
    await _add_agent(client, token, team["id"], "Frontend Engineer", role="Engineering")
    return team


async def test_team_execution_runs_all_active_agents(client):
    _, tokens = await create_authenticated_user(
        client, email="collab1@example.com", username="collab1"
    )
    token = tokens["access_token"]
    team = await _engineering_team(client, token)

    resp = await client.post(
        f"/v1/ai-teams/{team['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "Build a food delivery platform"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["team_id"] == team["id"]
    assert body["team_name"] == "Engineering Team"
    assert body["status"] == "COMPLETED"
    assert isinstance(body["execution_time_ms"], int)
    assert body["summary"]
    assert body["run_id"]
    assert len(body["steps"]) == 4
    assert all(step["response"] for step in body["steps"])


async def test_execution_ordering_role_priority(client):
    _, tokens = await create_authenticated_user(
        client, email="collab2@example.com", username="collab2"
    )
    token = tokens["access_token"]
    team = await _engineering_team(client, token)

    resp = await client.post(
        f"/v1/ai-teams/{team['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "Order matters"},
    )
    names = [s["agent_name"] for s in resp.json()["steps"]]
    # CTO -> Backend -> Frontend -> QA regardless of creation order.
    assert names == ["CTO", "Backend Engineer", "Frontend Engineer", "QA Engineer"]


async def test_context_propagation(client):
    _, tokens = await create_authenticated_user(
        client, email="collab3@example.com", username="collab3"
    )
    token = tokens["access_token"]
    team = await _make_team(client, token)
    await _add_agent(client, token, team["id"], "CTO", role="Leadership")
    await _add_agent(client, token, team["id"], "Backend Engineer", role="Engineering")

    resp = await client.post(
        f"/v1/ai-teams/{team['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "Design a system"},
    )
    run_id = resp.json()["run_id"]

    detail = await client.get(
        f"/v1/ai-teams/runs/{run_id}", headers=auth_headers(token)
    )
    assert detail.status_code == 200
    steps = sorted(detail.json()["steps"], key=lambda s: s["step_order"])
    # First agent: no prior outputs in its composed prompt.
    assert "(none" in steps[0]["prompt"]
    assert "Design a system" in steps[0]["prompt"]
    # Second agent: receives the first (CTO) agent's output as context.
    assert "CTO" in steps[1]["prompt"]
    assert steps[0]["response"][:30] in steps[1]["prompt"]


async def test_inactive_agents_excluded(client):
    _, tokens = await create_authenticated_user(
        client, email="collab4@example.com", username="collab4"
    )
    token = tokens["access_token"]
    team = await _make_team(client, token)
    await _add_agent(client, token, team["id"], "CTO", role="Leadership")
    await _add_agent(client, token, team["id"], "Sleeping Agent", active=False)

    resp = await client.post(
        f"/v1/ai-teams/{team['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "Only active"},
    )
    names = [s["agent_name"] for s in resp.json()["steps"]]
    assert names == ["CTO"]


async def test_execute_team_no_active_agents(client):
    _, tokens = await create_authenticated_user(
        client, email="collab5@example.com", username="collab5"
    )
    token = tokens["access_token"]
    team = await _make_team(client, token)
    await _add_agent(client, token, team["id"], "Sleeping Agent", active=False)

    resp = await client.post(
        f"/v1/ai-teams/{team['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "nobody home"},
    )
    assert resp.status_code == 400


async def test_history_persistence_and_listing(client):
    _, tokens = await create_authenticated_user(
        client, email="collab6@example.com", username="collab6"
    )
    token = tokens["access_token"]
    team = await _make_team(client, token)
    await _add_agent(client, token, team["id"], "CTO", role="Leadership")

    await client.post(
        f"/v1/ai-teams/{team['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "first run"},
    )
    await client.post(
        f"/v1/ai-teams/{team['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "second run"},
    )

    runs = await client.get(
        f"/v1/ai-teams/{team['id']}/runs", headers=auth_headers(token)
    )
    assert runs.status_code == 200
    body = runs.json()
    assert body["total"] == 2
    assert body["items"][0]["prompt"] == "second run"  # most recent first
    assert all(item["status"] == "COMPLETED" for item in body["items"])


async def test_failure_persists_failed_run_and_step(client, monkeypatch):
    from sqlalchemy import select

    from app.core.exceptions import AgentError
    from app.database.session import AsyncSessionLocal
    from app.models.ai_team import AITeamRun, AITeamRunStep

    _, tokens = await create_authenticated_user(
        client, email="collab7@example.com", username="collab7"
    )
    token = tokens["access_token"]
    team = await _make_team(client, token)
    await _add_agent(client, token, team["id"], "CTO", role="Leadership")
    await _add_agent(client, token, team["id"], "Backend Engineer", role="Engineering")

    call_count = {"n": 0}
    original = None

    async def maybe_boom(self, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 2:  # fail the second agent (Backend)
            raise AgentError("simulated provider outage")
        return await original(self, **kwargs)

    import app.services.ai_team_runner as runner_mod

    original = runner_mod.AITeamAgentRunner.run
    monkeypatch.setattr(runner_mod.AITeamAgentRunner, "run", maybe_boom)

    resp = await client.post(
        f"/v1/ai-teams/{team['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "this will fail mid-way"},
    )
    assert resp.status_code == 502
    assert "simulated provider outage" not in resp.text

    async with AsyncSessionLocal() as session:
        runs = (
            await session.execute(
                select(AITeamRun).where(AITeamRun.team_id == team["id"])
            )
        ).scalars().all()
        assert len(runs) == 1
        assert runs[0].status == "FAILED"
        run_id = runs[0].id
        steps = (
            await session.execute(
                select(AITeamRunStep)
                .where(AITeamRunStep.run_id == run_id)
                .order_by(AITeamRunStep.step_order)
            )
        ).scalars().all()
    # First step completed, second step recorded as FAILED, workflow stopped.
    assert len(steps) == 2
    assert steps[0].status == "COMPLETED"
    assert steps[1].status == "FAILED"
    assert steps[1].response is None


async def test_audit_events(client):
    from sqlalchemy import select

    from app.database.session import AsyncSessionLocal
    from app.models.audit import AuditLog

    _, tokens = await create_authenticated_user(
        client, email="collab8@example.com", username="collab8"
    )
    token = tokens["access_token"]
    team = await _make_team(client, token)
    await _add_agent(client, token, team["id"], "CTO", role="Leadership")

    resp = await client.post(
        f"/v1/ai-teams/{team['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "audit me"},
    )
    run_id = resp.json()["run_id"]

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.resource_type == "ai_team",
                    AuditLog.resource_id == team["id"],
                )
            )
        ).scalars().all()
    actions = {r.action for r in rows}
    assert "ai_team_execution_started" in actions
    assert "ai_team_execution_completed" in actions
    assert any(
        r.action == "ai_team_execution_completed"
        and (r.details or {}).get("run_id") == run_id
        for r in rows
    )


async def test_collaboration_tenant_isolation(client):
    _, tokens_a = await create_authenticated_user(
        client, email="collab-a@example.com", username="collabaa"
    )
    _, tokens_b = await create_authenticated_user(
        client, email="collab-b@example.com", username="collabbb"
    )
    token_a = tokens_a["access_token"]
    token_b = tokens_b["access_token"]
    team_a = await _make_team(client, token_a)
    await _add_agent(client, token_a, team_a["id"], "CTO", role="Leadership")

    run = await client.post(
        f"/v1/ai-teams/{team_a['id']}/execute",
        headers=auth_headers(token_a),
        json={"prompt": "own run"},
    )
    run_id = run.json()["run_id"]

    # Org B cannot execute Org A's team.
    intrusion = await client.post(
        f"/v1/ai-teams/{team_a['id']}/execute",
        headers=auth_headers(token_b),
        json={"prompt": "intrusion"},
    )
    assert intrusion.status_code == 404

    # Org B cannot list Org A's team runs.
    listing = await client.get(
        f"/v1/ai-teams/{team_a['id']}/runs", headers=auth_headers(token_b)
    )
    assert listing.status_code == 404

    # Org B cannot read Org A's run detail.
    detail = await client.get(
        f"/v1/ai-teams/runs/{run_id}", headers=auth_headers(token_b)
    )
    assert detail.status_code == 404


async def test_empty_prompt_rejected(client):
    _, tokens = await create_authenticated_user(
        client, email="collab9@example.com", username="collab9"
    )
    token = tokens["access_token"]
    team = await _make_team(client, token)
    await _add_agent(client, token, team["id"], "CTO", role="Leadership")
    resp = await client.post(
        f"/v1/ai-teams/{team['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": ""},
    )
    assert resp.status_code == 422
