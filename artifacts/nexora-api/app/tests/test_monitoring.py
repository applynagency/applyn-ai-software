"""Tests for Sprint 42A — Continuous Monitoring & Auto Incident Creation.

Covers alert ingestion, deduplication (occurrence_count + 30-min window), auto
incident creation, auto investigation trigger (reused 40A → timeline/40B,
recommendations/41A), the ALERT_DETECTED timeline event, notifications, the
dashboard, the scheduler tick, tenant isolation, audit logging, and no secret
leakage. No live infrastructure is touched (investigation degrades to its
deterministic offline path; notifications degrade to recorded sends).
"""

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.tests.conftest import auth_headers, create_authenticated_user


async def _team_agent(client, token):
    team = (await client.post("/v1/ai-teams", headers=auth_headers(token), json={"name": "Ops"})).json()
    await client.post(
        "/v1/ai-team-agents",
        headers=auth_headers(token),
        json={"team_id": team["id"], "name": "SRE", "role": "Ops", "instructions": "x",
              "model": "claude-sonnet", "temperature": 0.2, "max_tokens": 300, "is_active": True},
    )
    return team


def _alert(**over):
    base = {
        "provider": "PROMETHEUS",
        "alert_id": "alert-1",
        "alert_name": "HighErrorRate",
        "severity": "CRITICAL",
        "service": "checkout",
        "environment": "production",
        "description": "Error rate > 5%",
    }
    base.update(over)
    return base


async def _poll(client, token, alerts):
    return await client.post(
        "/v1/monitoring/poll", headers=auth_headers(token), json={"alerts": alerts}
    )


# ============================== ingestion ================================== #
async def test_alert_ingestion_creates_normalized_row(client):
    _, tokens = await create_authenticated_user(client, email="m1@e.com", username="mon1")
    token = tokens["access_token"]
    await _team_agent(client, token)

    resp = await _poll(client, token, [_alert(severity="warning")])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["alerts_ingested"] == 1
    assert body["new_alerts"] == 1
    a = body["alerts"][0]
    assert a["provider"] == "PROMETHEUS"
    assert a["severity"] == "WARNING"  # normalized from "warning"
    assert a["status"] == "FIRING"
    assert a["occurrence_count"] == 1


async def test_warning_alert_does_not_create_incident(client):
    _, tokens = await create_authenticated_user(client, email="m2@e.com", username="mon2")
    token = tokens["access_token"]
    await _team_agent(client, token)
    resp = await _poll(client, token, [_alert(severity="WARNING")])
    body = resp.json()
    assert body["incidents_created"] == 0
    assert body["alerts"][0]["incident_id"] is None


# ============================== deduplication ============================== #
async def test_deduplication_increments_occurrence(client):
    _, tokens = await create_authenticated_user(client, email="m3@e.com", username="mon3")
    token = tokens["access_token"]
    await _team_agent(client, token)

    r1 = (await _poll(client, token, [_alert()])).json()
    assert r1["new_alerts"] == 1 and r1["incidents_created"] == 1
    first_id = r1["alerts"][0]["id"]

    # Same provider/service/environment/alert name within window → dedup.
    r2 = (await _poll(client, token, [_alert(alert_id="alert-2")])).json()
    assert r2["new_alerts"] == 0
    assert r2["deduplicated"] == 1
    assert r2["incidents_created"] == 0
    assert r2["alerts"][0]["id"] == first_id
    assert r2["alerts"][0]["occurrence_count"] == 2

    # A different service is a distinct alert.
    r3 = (await _poll(client, token, [_alert(service="payments")])).json()
    assert r3["new_alerts"] == 1


# ============================== auto incident ============================== #
async def test_critical_alert_auto_creates_incident_and_links(client):
    _, tokens = await create_authenticated_user(client, email="m4@e.com", username="mon4")
    token = tokens["access_token"]
    await _team_agent(client, token)

    body = (await _poll(client, token, [_alert(severity="CRITICAL")])).json()
    assert body["incidents_created"] == 1
    incident_id = body["alerts"][0]["incident_id"]
    assert incident_id

    detail = (await client.get(f"/v1/incidents/{incident_id}", headers=auth_headers(token))).json()
    assert detail["source"] == "MONITORING"
    assert detail["severity"] == "CRITICAL"


async def test_auto_investigation_builds_timeline_with_alert_detected(client):
    _, tokens = await create_authenticated_user(client, email="m5@e.com", username="mon5")
    token = tokens["access_token"]
    await _team_agent(client, token)

    body = (await _poll(client, token, [_alert()])).json()
    incident_id = body["alerts"][0]["incident_id"]

    timeline = (await client.get(f"/v1/incidents/{incident_id}/timeline", headers=auth_headers(token))).json()
    events = timeline["timeline"]
    assert events, "expected a reconstructed timeline"
    # ALERT_DETECTED must be present and be the first (earliest) event.
    assert events[0]["event_type"] == "ALERT_DETECTED"
    assert any(e["event_type"] == "ALERT_DETECTED" for e in events)


async def test_auto_recommendations_generated(client):
    _, tokens = await create_authenticated_user(client, email="m6@e.com", username="mon6")
    token = tokens["access_token"]
    await _team_agent(client, token)

    body = (await _poll(client, token, [_alert()])).json()
    incident_id = body["alerts"][0]["incident_id"]
    recs = (await client.get(f"/v1/incidents/{incident_id}/recommendations", headers=auth_headers(token))).json()
    assert len(recs["recommendations"]) >= 1


async def test_auto_incident_without_team_still_created(client):
    # No AI team configured → incident is still auto-created (fallback path).
    _, tokens = await create_authenticated_user(client, email="m7@e.com", username="mon7")
    token = tokens["access_token"]
    body = (await _poll(client, token, [_alert()])).json()
    assert body["incidents_created"] == 1
    incident_id = body["alerts"][0]["incident_id"]
    detail = (await client.get(f"/v1/incidents/{incident_id}", headers=auth_headers(token))).json()
    assert detail["source"] == "MONITORING"


# ============================== notifications ============================== #
async def test_notification_sent_on_incident(client):
    _, tokens = await create_authenticated_user(client, email="m8@e.com", username="mon8")
    token = tokens["access_token"]
    await _team_agent(client, token)

    body = (await _poll(client, token, [_alert()])).json()
    assert body["notifications_sent"] >= 1

    async with AsyncSessionLocal() as session:
        actions = {r.action for r in (await session.execute(select(AuditLog))).scalars().all()}
    assert "incident_notification_sent" in actions
    assert "monitoring_incident_created" in actions


# ============================== dashboard ================================== #
async def test_dashboard_aggregates(client):
    _, tokens = await create_authenticated_user(client, email="m9@e.com", username="mon9")
    token = tokens["access_token"]
    await _team_agent(client, token)
    await _poll(client, token, [_alert(), _alert(service="payments", severity="WARNING")])

    resp = await client.get("/v1/monitoring/dashboard", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    d = resp.json()
    assert d["active_alerts"] >= 2
    assert len(d["incident_trend"]) == 8
    assert d["top_affected_services"]
    assert d["total_incidents"] >= 1


async def test_list_and_get_alert(client):
    _, tokens = await create_authenticated_user(client, email="m10@e.com", username="mon10")
    token = tokens["access_token"]
    await _team_agent(client, token)
    body = (await _poll(client, token, [_alert()])).json()
    alert_id = body["alerts"][0]["id"]

    lst = (await client.get("/v1/monitoring/alerts", headers=auth_headers(token))).json()
    assert lst["total"] >= 1
    one = await client.get(f"/v1/monitoring/alerts/{alert_id}", headers=auth_headers(token))
    assert one.status_code == 200
    assert one.json()["id"] == alert_id


# ============================== tenant isolation =========================== #
async def test_tenant_isolation(client):
    _, tok_a = await create_authenticated_user(client, email="ta@e.com", username="monta")
    _, tok_b = await create_authenticated_user(client, email="tb@e.com", username="montb")
    await _team_agent(client, tok_a["access_token"])
    body = (await _poll(client, tok_a["access_token"], [_alert()])).json()
    alert_id = body["alerts"][0]["id"]

    # Org B cannot see org A's alerts.
    lst_b = (await client.get("/v1/monitoring/alerts", headers=auth_headers(tok_b["access_token"]))).json()
    assert lst_b["total"] == 0
    cross = await client.get(f"/v1/monitoring/alerts/{alert_id}", headers=auth_headers(tok_b["access_token"]))
    assert cross.status_code == 404


# ============================== audit + no leak ============================ #
async def test_audit_logging_and_no_secret_leak(client):
    _, tokens = await create_authenticated_user(client, email="m11@e.com", username="mon11")
    token = tokens["access_token"]
    await _team_agent(client, token)
    # Connect a credential carrying a secret; monitoring must never surface it.
    await client.post("/v1/credentials", headers=auth_headers(token),
                      json={"provider": "PROMETHEUS", "name": "prom",
                            "secret": {"endpoint": "http://x", "token": "SUPER-SECRET-TOKEN-XYZ"}})
    resp = await _poll(client, token, [_alert()])
    assert "SUPER-SECRET-TOKEN-XYZ" not in resp.text

    async with AsyncSessionLocal() as session:
        actions = {r.action for r in (await session.execute(select(AuditLog))).scalars().all()}
    assert "monitoring_poll_completed" in actions
    assert "monitoring_alert_created" in actions

    dash = await client.get("/v1/monitoring/dashboard", headers=auth_headers(token))
    assert "SUPER-SECRET-TOKEN-XYZ" not in dash.text


async def test_poll_requires_auth(client):
    resp = await client.post("/v1/monitoring/poll", json={"alerts": [_alert()]})
    assert resp.status_code in (401, 403)


# ============================== scheduler ================================== #
async def test_scheduler_runner_polls_orgs_with_monitoring_creds(client):
    from app.services.monitoring_scheduler import MonitoringSchedulerRunner

    _, tokens = await create_authenticated_user(client, email="sch@e.com", username="sch")
    token = tokens["access_token"]
    await _team_agent(client, token)
    # Connect a monitoring provider so the org is in scope for the scheduler.
    await client.post("/v1/credentials", headers=auth_headers(token),
                      json={"provider": "DATADOG", "name": "dd", "secret": {"api_key": "k", "app_key": "a"}})

    async with AsyncSessionLocal() as session:
        polled = await MonitoringSchedulerRunner().run_once(session)
    # The org is discovered and polled (no provided alerts → 0 ingested, but it ran).
    assert polled >= 1
