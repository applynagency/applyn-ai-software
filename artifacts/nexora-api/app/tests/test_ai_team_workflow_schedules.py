"""Tests for Sprint 38B — Scheduled Workflow Runs."""

from datetime import UTC, timedelta

from app.tests.conftest import auth_headers, create_authenticated_user


async def _make_workflow(client, token, name="Engineering Workflow"):
    team = (
        await client.post("/v1/ai-teams", headers=auth_headers(token), json={"name": "Eng Team"})
    ).json()
    cto = (
        await client.post(
            "/v1/ai-team-agents",
            headers=auth_headers(token),
            json={
                "team_id": team["id"],
                "name": "CTO",
                "role": "Leadership",
                "instructions": "You are the CTO.",
                "model": "claude-sonnet",
                "temperature": 0.3,
                "max_tokens": 300,
                "is_active": True,
            },
        )
    ).json()
    wf = (
        await client.post(
            "/v1/ai-team-workflows",
            headers=auth_headers(token),
            json={
                "team_id": team["id"],
                "name": name,
                "default_prompt": "Review all architecture decisions from yesterday.",
                "steps": [{"agent_id": cto["id"], "step_order": 1}],
            },
        )
    ).json()
    return wf


async def _create_schedule(client, token, workflow_id, **overrides):
    payload = {
        "workflow_id": workflow_id,
        "name": "Daily Engineering Review",
        "schedule_type": "DAILY",
        "cron_expression": "0 9 * * *",
        "timezone": "UTC",
        "prompt_template": "Review all architecture decisions from yesterday.",
        "is_active": True,
    }
    payload.update(overrides)
    return await client.post(
        "/v1/ai-team-workflow-schedules", headers=auth_headers(token), json=payload
    )


async def test_schedule_crud(client):
    _, tokens = await create_authenticated_user(
        client, email="sch1@example.com", username="sch1"
    )
    token = tokens["access_token"]
    wf = await _make_workflow(client, token)

    created = await _create_schedule(client, token, wf["id"])
    assert created.status_code == 201, created.text
    sch = created.json()
    assert sch["name"] == "Daily Engineering Review"
    assert sch["schedule_type"] == "DAILY"
    assert sch["workflow_name"] == "Engineering Workflow"
    assert sch["next_run_at"] is not None  # next_run_at calculated on create

    got = await client.get(
        f"/v1/ai-team-workflow-schedules/{sch['id']}", headers=auth_headers(token)
    )
    assert got.status_code == 200

    listing = await client.get("/v1/ai-team-workflow-schedules", headers=auth_headers(token))
    assert listing.json()["total"] == 1

    updated = await client.put(
        f"/v1/ai-team-workflow-schedules/{sch['id']}",
        headers=auth_headers(token),
        json={"name": "Renamed Review", "cron_expression": "30 8 * * 1", "schedule_type": "WEEKLY"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed Review"
    assert updated.json()["schedule_type"] == "WEEKLY"

    deleted = await client.delete(
        f"/v1/ai-team-workflow-schedules/{sch['id']}", headers=auth_headers(token)
    )
    assert deleted.status_code == 204
    assert (
        await client.get("/v1/ai-team-workflow-schedules", headers=auth_headers(token))
    ).json()["total"] == 0


async def test_invalid_cron_rejected(client):
    _, tokens = await create_authenticated_user(
        client, email="sch2@example.com", username="sch2"
    )
    token = tokens["access_token"]
    wf = await _make_workflow(client, token)
    resp = await _create_schedule(client, token, wf["id"], cron_expression="not a cron")
    assert resp.status_code == 422


async def test_invalid_timezone_rejected(client):
    _, tokens = await create_authenticated_user(
        client, email="sch3@example.com", username="sch3"
    )
    token = tokens["access_token"]
    wf = await _make_workflow(client, token)
    resp = await _create_schedule(client, token, wf["id"], timezone="Mars/Olympus")
    assert resp.status_code == 422


async def test_next_run_calculation_timezone():
    from datetime import datetime

    from app.services.workflow_scheduler import compute_next_run

    base = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    # 9am daily in New York == 14:00 UTC (EST, winter).
    nxt = compute_next_run("0 9 * * *", "America/New_York", base)
    assert nxt > base
    assert nxt.hour == 14
    assert nxt.tzinfo is not None


async def test_manual_run_now_creates_scheduled_run(client):
    _, tokens = await create_authenticated_user(
        client, email="sch4@example.com", username="sch4"
    )
    token = tokens["access_token"]
    wf = await _make_workflow(client, token)
    sch = (await _create_schedule(client, token, wf["id"])).json()

    resp = await client.post(
        f"/v1/ai-team-workflow-schedules/{sch['id']}/run-now", headers=auth_headers(token)
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "COMPLETED"
    assert resp.json()["execution_source"] == "SCHEDULED"

    runs = await client.get(
        f"/v1/ai-team-workflows/{wf['id']}/runs", headers=auth_headers(token)
    )
    assert runs.json()["total"] == 1
    assert runs.json()["items"][0]["execution_source"] == "SCHEDULED"

    # last_run_at recorded by run-now
    got = await client.get(
        f"/v1/ai-team-workflow-schedules/{sch['id']}", headers=auth_headers(token)
    )
    assert got.json()["last_run_at"] is not None


async def test_manual_execute_is_marked_manual(client):
    _, tokens = await create_authenticated_user(
        client, email="sch5@example.com", username="sch5"
    )
    token = tokens["access_token"]
    wf = await _make_workflow(client, token)
    await client.post(
        f"/v1/ai-team-workflows/{wf['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "manual run"},
    )
    runs = await client.get(
        f"/v1/ai-team-workflows/{wf['id']}/runs", headers=auth_headers(token)
    )
    assert runs.json()["items"][0]["execution_source"] == "MANUAL"


async def test_scheduler_tick_executes_due_schedule(client):
    from sqlalchemy import select

    from app.database.base import utcnow
    from app.database.session import AsyncSessionLocal
    from app.models.ai_team import AITeamWorkflowSchedule
    from app.services.workflow_scheduler import WorkflowSchedulerRunner

    _, tokens = await create_authenticated_user(
        client, email="sch6@example.com", username="sch6"
    )
    token = tokens["access_token"]
    wf = await _make_workflow(client, token)
    sch = (await _create_schedule(client, token, wf["id"])).json()

    # Force the schedule due in the past.
    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                select(AITeamWorkflowSchedule).where(AITeamWorkflowSchedule.id == sch["id"])
            )
        ).scalar_one()
        past_next = row.next_run_at
        row.next_run_at = utcnow() - timedelta(minutes=1)
        await session.commit()

    # Run one scheduler tick.
    async with AsyncSessionLocal() as session:
        triggered = await WorkflowSchedulerRunner().run_due_schedules(session)
    assert triggered == 1

    # A SCHEDULED run was created automatically.
    runs = await client.get(
        f"/v1/ai-team-workflows/{wf['id']}/runs", headers=auth_headers(token)
    )
    body = runs.json()
    assert body["total"] == 1
    assert body["items"][0]["execution_source"] == "SCHEDULED"
    assert body["items"][0]["status"] == "COMPLETED"

    # Schedule advanced: next_run_at moved into the future, last_run_at set.
    got = (
        await client.get(
            f"/v1/ai-team-workflow-schedules/{sch['id']}", headers=auth_headers(token)
        )
    ).json()
    assert got["last_run_at"] is not None
    assert got["next_run_at"] is not None


async def test_scheduler_skips_inactive_schedule(client):
    from datetime import datetime

    from sqlalchemy import select

    from app.database.session import AsyncSessionLocal
    from app.models.ai_team import AITeamWorkflowSchedule
    from app.services.workflow_scheduler import WorkflowSchedulerRunner

    _, tokens = await create_authenticated_user(
        client, email="sch7@example.com", username="sch7"
    )
    token = tokens["access_token"]
    wf = await _make_workflow(client, token)
    sch = (await _create_schedule(client, token, wf["id"], is_active=False)).json()
    assert sch["next_run_at"] is None  # inactive => no scheduled time

    # Even if we backdate it, an inactive schedule is not selected by list_due.
    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                select(AITeamWorkflowSchedule).where(AITeamWorkflowSchedule.id == sch["id"])
            )
        ).scalar_one()
        row.next_run_at = datetime(2020, 1, 1, tzinfo=UTC)
        await session.commit()
    async with AsyncSessionLocal() as session:
        triggered = await WorkflowSchedulerRunner().run_due_schedules(session)
    assert triggered == 0


async def test_schedule_tenant_isolation(client):
    _, tokens_a = await create_authenticated_user(
        client, email="sch-a@example.com", username="schaa"
    )
    _, tokens_b = await create_authenticated_user(
        client, email="sch-b@example.com", username="schbb"
    )
    token_a = tokens_a["access_token"]
    token_b = tokens_b["access_token"]
    wf = await _make_workflow(client, token_a)
    sch = (await _create_schedule(client, token_a, wf["id"])).json()

    assert (
        await client.get(
            f"/v1/ai-team-workflow-schedules/{sch['id']}", headers=auth_headers(token_b)
        )
    ).status_code == 404
    assert (
        await client.post(
            f"/v1/ai-team-workflow-schedules/{sch['id']}/run-now", headers=auth_headers(token_b)
        )
    ).status_code == 404
    assert (
        await client.delete(
            f"/v1/ai-team-workflow-schedules/{sch['id']}", headers=auth_headers(token_b)
        )
    ).status_code == 404
    assert (
        await client.get("/v1/ai-team-workflow-schedules", headers=auth_headers(token_b))
    ).json()["total"] == 0
    # Org B cannot schedule against Org A's workflow either.
    assert (await _create_schedule(client, token_b, wf["id"])).status_code == 404


async def test_schedule_audit_events(client):
    from sqlalchemy import select

    from app.database.session import AsyncSessionLocal
    from app.models.audit import AuditLog

    _, tokens = await create_authenticated_user(
        client, email="sch8@example.com", username="sch8"
    )
    token = tokens["access_token"]
    wf = await _make_workflow(client, token)
    sch = (await _create_schedule(client, token, wf["id"])).json()
    await client.post(
        f"/v1/ai-team-workflow-schedules/{sch['id']}/run-now", headers=auth_headers(token)
    )

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(AuditLog).where(AuditLog.resource_id == sch["id"])
            )
        ).scalars().all()
    actions = {r.action for r in rows}
    assert "workflow_schedule_created" in actions
    assert "workflow_schedule_triggered" in actions
