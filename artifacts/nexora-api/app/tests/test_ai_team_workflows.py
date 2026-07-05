"""Tests for Sprint 38A — Reusable Team Workflows."""

from app.tests.conftest import auth_headers, create_authenticated_user


async def _make_team(client, token, name="Engineering Team"):
    return (
        await client.post(
            "/v1/ai-teams", headers=auth_headers(token), json={"name": name}
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
                "max_tokens": 400,
                "is_active": active,
            },
        )
    ).json()


async def _engineering_team(client, token):
    team = await _make_team(client, token)
    cto = await _add_agent(client, token, team["id"], "CTO", role="Leadership")
    backend = await _add_agent(client, token, team["id"], "Backend Engineer")
    frontend = await _add_agent(client, token, team["id"], "Frontend Engineer")
    qa = await _add_agent(client, token, team["id"], "QA Engineer", role="Quality")
    return team, [cto, backend, frontend, qa]


async def _create_workflow(client, token, team_id, agents, name="Engineering Workflow"):
    steps = [
        {"agent_id": a["id"], "step_order": i + 1} for i, a in enumerate(agents)
    ]
    return await client.post(
        "/v1/ai-team-workflows",
        headers=auth_headers(token),
        json={
            "team_id": team_id,
            "name": name,
            "description": "Standard build flow",
            "default_prompt": "Build a CRM for healthcare clinics",
            "steps": steps,
        },
    )


async def test_workflow_crud(client):
    _, tokens = await create_authenticated_user(
        client, email="wf1@example.com", username="wf1"
    )
    token = tokens["access_token"]
    team, agents = await _engineering_team(client, token)

    created = await _create_workflow(client, token, team["id"], agents)
    assert created.status_code == 201, created.text
    wf = created.json()
    assert wf["name"] == "Engineering Workflow"
    assert wf["team_name"] == "Engineering Team"
    assert wf["step_count"] == 4
    assert [s["agent_name"] for s in wf["steps"]] == [
        "CTO", "Backend Engineer", "Frontend Engineer", "QA Engineer"
    ]

    # Read
    got = await client.get(
        f"/v1/ai-team-workflows/{wf['id']}", headers=auth_headers(token)
    )
    assert got.status_code == 200
    assert got.json()["step_count"] == 4

    # List
    listing = await client.get("/v1/ai-team-workflows", headers=auth_headers(token))
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    # Update (rename + reduce steps)
    updated = await client.put(
        f"/v1/ai-team-workflows/{wf['id']}",
        headers=auth_headers(token),
        json={
            "name": "Lean Engineering Workflow",
            "steps": [
                {"agent_id": agents[0]["id"], "step_order": 1},
                {"agent_id": agents[1]["id"], "step_order": 2},
            ],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Lean Engineering Workflow"
    assert updated.json()["step_count"] == 2

    # Delete
    deleted = await client.delete(
        f"/v1/ai-team-workflows/{wf['id']}", headers=auth_headers(token)
    )
    assert deleted.status_code == 204
    listing2 = await client.get("/v1/ai-team-workflows", headers=auth_headers(token))
    assert listing2.json()["total"] == 0


async def test_workflow_step_must_belong_to_team(client):
    _, tokens = await create_authenticated_user(
        client, email="wf2@example.com", username="wf2"
    )
    token = tokens["access_token"]
    team, _ = await _engineering_team(client, token)
    # An agent from a different team is invalid.
    other_team, other_agents = await _engineering_team(client, token)

    resp = await client.post(
        "/v1/ai-team-workflows",
        headers=auth_headers(token),
        json={
            "team_id": team["id"],
            "name": "Bad Workflow",
            "steps": [{"agent_id": other_agents[0]["id"], "step_order": 1}],
        },
    )
    assert resp.status_code == 422


async def test_workflow_execution_and_ordering(client):
    _, tokens = await create_authenticated_user(
        client, email="wf3@example.com", username="wf3"
    )
    token = tokens["access_token"]
    team, agents = await _engineering_team(client, token)
    # Define an explicit (non-role) order: QA first, then CTO, then Backend.
    steps = [
        {"agent_id": agents[3]["id"], "step_order": 1},  # QA
        {"agent_id": agents[0]["id"], "step_order": 2},  # CTO
        {"agent_id": agents[1]["id"], "step_order": 3},  # Backend
    ]
    wf = (
        await client.post(
            "/v1/ai-team-workflows",
            headers=auth_headers(token),
            json={"team_id": team["id"], "name": "Custom Order", "steps": steps},
        )
    ).json()

    resp = await client.post(
        f"/v1/ai-team-workflows/{wf['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "Build a CRM for healthcare clinics"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["workflow_name"] == "Custom Order"
    assert body["run_id"]
    # Executes in workflow-defined order, not role priority.
    assert [s["agent_name"] for s in body["steps"]] == [
        "QA Engineer", "CTO", "Backend Engineer"
    ]


async def test_workflow_execution_uses_default_prompt(client):
    _, tokens = await create_authenticated_user(
        client, email="wf4@example.com", username="wf4"
    )
    token = tokens["access_token"]
    team, agents = await _engineering_team(client, token)
    wf = (await _create_workflow(client, token, team["id"], agents[:1])).json()

    # No prompt in request -> falls back to the workflow default_prompt.
    resp = await client.post(
        f"/v1/ai-team-workflows/{wf['id']}/execute",
        headers=auth_headers(token),
        json={},
    )
    assert resp.status_code == 200, resp.text
    assert "Build a CRM for healthcare clinics" in resp.json()["steps"][0]["response"]


async def test_workflow_history_persisted(client):
    _, tokens = await create_authenticated_user(
        client, email="wf5@example.com", username="wf5"
    )
    token = tokens["access_token"]
    team, agents = await _engineering_team(client, token)
    wf = (await _create_workflow(client, token, team["id"], agents[:1])).json()

    await client.post(
        f"/v1/ai-team-workflows/{wf['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "first"},
    )
    await client.post(
        f"/v1/ai-team-workflows/{wf['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "second"},
    )
    runs = await client.get(
        f"/v1/ai-team-workflows/{wf['id']}/runs", headers=auth_headers(token)
    )
    assert runs.status_code == 200
    body = runs.json()
    assert body["total"] == 2
    assert body["items"][0]["prompt"] == "second"  # most recent first
    assert all(r["status"] == "COMPLETED" for r in body["items"])


async def test_workflow_inactive_agents_skipped(client):
    _, tokens = await create_authenticated_user(
        client, email="wf6@example.com", username="wf6"
    )
    token = tokens["access_token"]
    team = await _make_team(client, token)
    cto = await _add_agent(client, token, team["id"], "CTO", role="Leadership")
    sleeper = await _add_agent(client, token, team["id"], "Sleeper", active=False)
    wf = (
        await client.post(
            "/v1/ai-team-workflows",
            headers=auth_headers(token),
            json={
                "team_id": team["id"],
                "name": "Has Inactive",
                "steps": [
                    {"agent_id": cto["id"], "step_order": 1},
                    {"agent_id": sleeper["id"], "step_order": 2},
                ],
            },
        )
    ).json()
    resp = await client.post(
        f"/v1/ai-team-workflows/{wf['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "go"},
    )
    assert resp.status_code == 200
    assert [s["agent_name"] for s in resp.json()["steps"]] == ["CTO"]


async def test_workflow_failure_persists_failed_run(client, monkeypatch):
    from sqlalchemy import select

    from app.core.exceptions import AgentError
    from app.database.session import AsyncSessionLocal
    from app.models.ai_team import AITeamWorkflowRun

    _, tokens = await create_authenticated_user(
        client, email="wf7@example.com", username="wf7"
    )
    token = tokens["access_token"]
    team, agents = await _engineering_team(client, token)
    wf = (await _create_workflow(client, token, team["id"], agents[:2])).json()

    async def boom(self, **kwargs):
        raise AgentError("simulated provider outage")

    monkeypatch.setattr("app.services.ai_team_runner.AITeamAgentRunner.run", boom)

    resp = await client.post(
        f"/v1/ai-team-workflows/{wf['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "will fail"},
    )
    assert resp.status_code == 502
    assert "simulated provider outage" not in resp.text

    async with AsyncSessionLocal() as session:
        runs = (
            await session.execute(
                select(AITeamWorkflowRun).where(AITeamWorkflowRun.workflow_id == wf["id"])
            )
        ).scalars().all()
    assert len(runs) == 1
    assert runs[0].status == "FAILED"


async def test_workflow_tenant_isolation(client):
    _, tokens_a = await create_authenticated_user(
        client, email="wf-a@example.com", username="wfaa"
    )
    _, tokens_b = await create_authenticated_user(
        client, email="wf-b@example.com", username="wfbb"
    )
    token_a = tokens_a["access_token"]
    token_b = tokens_b["access_token"]
    team_a, agents_a = await _engineering_team(client, token_a)
    wf_a = (await _create_workflow(client, token_a, team_a["id"], agents_a[:1])).json()

    # Org B cannot read, execute, list runs, update, or delete Org A's workflow.
    assert (
        await client.get(
            f"/v1/ai-team-workflows/{wf_a['id']}", headers=auth_headers(token_b)
        )
    ).status_code == 404
    assert (
        await client.post(
            f"/v1/ai-team-workflows/{wf_a['id']}/execute",
            headers=auth_headers(token_b),
            json={"prompt": "intrusion"},
        )
    ).status_code == 404
    assert (
        await client.get(
            f"/v1/ai-team-workflows/{wf_a['id']}/runs", headers=auth_headers(token_b)
        )
    ).status_code == 404
    assert (
        await client.delete(
            f"/v1/ai-team-workflows/{wf_a['id']}", headers=auth_headers(token_b)
        )
    ).status_code == 404
    # Org B's workflow list does not include Org A's workflow.
    listing_b = await client.get("/v1/ai-team-workflows", headers=auth_headers(token_b))
    assert listing_b.json()["total"] == 0


async def test_workflow_audit_events(client):
    from sqlalchemy import select

    from app.database.session import AsyncSessionLocal
    from app.models.audit import AuditLog

    _, tokens = await create_authenticated_user(
        client, email="wf8@example.com", username="wf8"
    )
    token = tokens["access_token"]
    team, agents = await _engineering_team(client, token)
    wf = (await _create_workflow(client, token, team["id"], agents[:1])).json()
    await client.post(
        f"/v1/ai-team-workflows/{wf['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "audit me"},
    )

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(AuditLog).where(AuditLog.resource_id == wf["id"])
            )
        ).scalars().all()
    actions = {r.action for r in rows}
    assert "workflow_created" in actions
    assert "workflow_executed" in actions
