"""DevOps & SRE workspace integration tests."""

from __future__ import annotations

import pytest

from app.tests.conftest import auth_headers, create_authenticated_user


@pytest.mark.asyncio
async def test_ops_workspace_my_work_and_queue(client):
    _, tokens = await create_authenticated_user(client, email="ops1@e.com", username="opsuser1")
    token = tokens["access_token"]

    my_work = await client.get("/v1/ops-workspace/my-work", headers=auth_headers(token))
    assert my_work.status_code == 200, my_work.text
    body = my_work.json()
    assert "sections" in body
    assert "total_attention_items" in body

    queue = await client.get("/v1/ops-workspace/queue", headers=auth_headers(token))
    assert queue.status_code == 200
    assert "items" in queue.json()
    assert "total" in queue.json()


@pytest.mark.asyncio
async def test_ops_workspace_changes_maintenance_calendar(client):
    _, tokens = await create_authenticated_user(client, email="ops2@e.com", username="opsuser2")
    token = tokens["access_token"]

    changes = await client.get("/v1/ops-workspace/changes", headers=auth_headers(token))
    assert changes.status_code == 200
    assert "events" in changes.json()

    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    maint = await client.post(
        "/v1/ops-workspace/maintenance",
        headers=auth_headers(token),
        json={
            "kind": "WINDOW",
            "title": "Cluster upgrade",
            "starts_at": (now + timedelta(days=1)).isoformat(),
            "ends_at": (now + timedelta(days=1, hours=2)).isoformat(),
            "impact_summary": "Brief API latency increase",
        },
    )
    assert maint.status_code == 201, maint.text
    window_id = maint.json()["id"]

    decide = await client.post(
        f"/v1/ops-workspace/maintenance/{window_id}/decide?approved=true",
        headers=auth_headers(token),
    )
    assert decide.status_code == 200

    calendar = await client.get("/v1/ops-workspace/calendar", headers=auth_headers(token))
    assert calendar.status_code == 200
    assert len(calendar.json()) >= 1


@pytest.mark.asyncio
async def test_ops_workspace_slo_cost_executive_kpis(client):
    _, tokens = await create_authenticated_user(client, email="ops3@e.com", username="opsuser3")
    token = tokens["access_token"]

    for path in ("/slo", "/cost", "/executive", "/kpis"):
        r = await client.get(f"/v1/ops-workspace{path}", headers=auth_headers(token))
        assert r.status_code == 200, r.text

    pdf = await client.get("/v1/ops-workspace/executive/export/pdf", headers=auth_headers(token))
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"


@pytest.mark.asyncio
async def test_ops_workspace_briefing_handover_search_ai(client):
    _, tokens = await create_authenticated_user(client, email="ops4@e.com", username="opsuser4")
    token = tokens["access_token"]

    briefing = await client.post("/v1/ops-workspace/briefing/daily", headers=auth_headers(token))
    assert briefing.status_code == 201, briefing.text
    assert briefing.json()["summary"]

    latest = await client.get("/v1/ops-workspace/briefing/daily/latest", headers=auth_headers(token))
    assert latest.status_code == 200

    handover = await client.post("/v1/ops-workspace/handover", headers=auth_headers(token))
    assert handover.status_code == 201, handover.text
    handover_id = handover.json()["id"]

    pdf = await client.get(
        f"/v1/ops-workspace/handover/{handover_id}/export/pdf",
        headers=auth_headers(token),
    )
    assert pdf.status_code == 200

    search = await client.get("/v1/ops-workspace/search?q=incident", headers=auth_headers(token))
    assert search.status_code == 200

    suggestions = await client.get(
        "/v1/ops-workspace/automation-suggestions", headers=auth_headers(token),
    )
    assert suggestions.status_code == 200

    ctx = await client.post(
        "/v1/ops-workspace/ai-context",
        headers=auth_headers(token),
        json={"page": "queue", "question": "What needs attention?"},
    )
    assert ctx.status_code == 200
    assert "suggested_questions" in ctx.json()
