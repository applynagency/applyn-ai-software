"""Tests for Sprint 42B — Intelligent On-Call & Escalation Engine.

Covers service ownership CRUD, timezone-aware rotation resolution, escalation
policy CRUD, automatic incident routing (owner + on-call + approver) on
monitoring-created incidents, the acknowledgement flow + states, escalation
timing, MTTA/MTTR metrics, notifications, tenant isolation, and audit logging.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.models.oncall import IncidentAssignment
from app.services.oncall import EscalationEngine, resolve_current_oncall
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
    base = {"provider": "PROMETHEUS", "alert_id": "a1", "alert_name": "HighErrorRate",
            "severity": "CRITICAL", "service": "checkout", "environment": "production"}
    base.update(over)
    return base


async def _poll(client, token, alerts):
    return await client.post("/v1/monitoring/poll", headers=auth_headers(token), json={"alerts": alerts})


# ============================== rotation math (unit) ======================= #
def test_daily_rotation_resolution():
    anchor = datetime(2026, 1, 1, tzinfo=UTC)
    sched = SimpleNamespace(participants=["u0", "u1", "u2"], timezone="UTC",
                            rotation_type="DAILY", anchor_at=anchor)
    assert resolve_current_oncall(sched, anchor) == "u0"
    assert resolve_current_oncall(sched, anchor + timedelta(days=1)) == "u1"
    assert resolve_current_oncall(sched, anchor + timedelta(days=3)) == "u0"


def test_weekly_rotation_resolution():
    anchor = datetime(2026, 1, 1, tzinfo=UTC)
    sched = SimpleNamespace(participants=["a", "b"], timezone="UTC",
                            rotation_type="WEEKLY", anchor_at=anchor)
    assert resolve_current_oncall(sched, anchor + timedelta(days=2)) == "a"
    assert resolve_current_oncall(sched, anchor + timedelta(days=8)) == "b"
    assert resolve_current_oncall(sched, anchor + timedelta(days=15)) == "a"


def test_empty_rotation_returns_none():
    sched = SimpleNamespace(participants=[], timezone="UTC", rotation_type="DAILY",
                            anchor_at=datetime(2026, 1, 1, tzinfo=UTC))
    assert resolve_current_oncall(sched) is None


# ============================== ownership CRUD ============================= #
async def test_service_owner_crud(client):
    me, tokens = await create_authenticated_user(client, email="oc1@e.com", username="onc1")
    token = tokens["access_token"]
    uid = me["id"]
    created = await client.post("/v1/oncall/service-owners", headers=auth_headers(token),
                                json={"service_name": "checkout", "primary_owner_id": uid,
                                      "team": "payments", "escalation_group": "pay-oncall"})
    assert created.status_code == 201, created.text
    owner_id = created.json()["id"]

    lst = (await client.get("/v1/oncall/service-owners", headers=auth_headers(token))).json()
    assert len(lst) == 1 and lst[0]["service_name"] == "checkout"

    upd = await client.patch(f"/v1/oncall/service-owners/{owner_id}", headers=auth_headers(token),
                             json={"team": "checkout-team"})
    assert upd.status_code == 200 and upd.json()["team"] == "checkout-team"

    d = await client.delete(f"/v1/oncall/service-owners/{owner_id}", headers=auth_headers(token))
    assert d.status_code == 204


# ============================== schedule CRUD ============================== #
async def test_schedule_crud_and_current_oncall(client):
    me, tokens = await create_authenticated_user(client, email="oc2@e.com", username="onc2")
    token = tokens["access_token"]
    uid = me["id"]
    created = await client.post("/v1/oncall/schedules", headers=auth_headers(token),
                                json={"name": "Primary", "team": "payments", "rotation_type": "WEEKLY",
                                      "timezone": "UTC", "participants": [uid]})
    assert created.status_code == 201, created.text
    assert created.json()["current_oncall_user_id"] == uid

    cur = (await client.get("/v1/oncall/current", headers=auth_headers(token))).json()
    assert any(c["user_id"] == uid for c in cur)


async def test_escalation_policy_crud(client):
    me, tokens = await create_authenticated_user(client, email="oc3@e.com", username="onc3")
    token = tokens["access_token"]
    uid = me["id"]
    created = await client.post("/v1/oncall/escalation-policies", headers=auth_headers(token),
                                json={"name": "Default", "service_name": None,
                                      "steps": [{"after_minutes": 10, "target_type": "SECONDARY_OWNER"},
                                                {"after_minutes": 20, "target_type": "MANAGEMENT", "target_user_id": uid}]})
    assert created.status_code == 201, created.text
    body = created.json()
    assert len(body["steps"]) == 2
    assert body["steps"][0]["after_minutes"] == 10

    lst = (await client.get("/v1/oncall/escalation-policies", headers=auth_headers(token))).json()
    assert len(lst) == 1


# ============================== routing =================================== #
async def test_incident_auto_routed_to_oncall(client):
    me, tokens = await create_authenticated_user(client, email="oc4@e.com", username="onc4")
    token = tokens["access_token"]
    uid = me["id"]
    await _team_agent(client, token)
    await client.post("/v1/oncall/service-owners", headers=auth_headers(token),
                      json={"service_name": "checkout", "primary_owner_id": uid, "team": "payments"})
    await client.post("/v1/oncall/schedules", headers=auth_headers(token),
                      json={"name": "Primary", "team": "payments", "participants": [uid]})

    body = (await _poll(client, token, [_alert()])).json()
    incident_id = body["alerts"][0]["incident_id"]
    assert incident_id

    a = (await client.get(f"/v1/oncall/incidents/{incident_id}/assignment", headers=auth_headers(token))).json()
    assert a["service_name"] == "checkout"
    assert a["responder_id"] == uid  # current on-call
    assert a["owner_id"] == uid      # primary owner
    assert a["approver_id"] == uid
    assert a["state"] == "OPEN"


async def test_routing_without_config_still_assigns(client):
    _, tokens = await create_authenticated_user(client, email="oc5@e.com", username="onc5")
    token = tokens["access_token"]
    await _team_agent(client, token)
    body = (await _poll(client, token, [_alert()])).json()
    incident_id = body["alerts"][0]["incident_id"]
    a = (await client.get(f"/v1/oncall/incidents/{incident_id}/assignment", headers=auth_headers(token))).json()
    assert a["state"] == "OPEN"  # assignment created even without owner/schedule


# ============================== acknowledgement =========================== #
async def test_acknowledgement_flow_and_mtta(client):
    me, tokens = await create_authenticated_user(client, email="oc6@e.com", username="onc6")
    token = tokens["access_token"]
    uid = me["id"]
    await _team_agent(client, token)
    await client.post("/v1/oncall/schedules", headers=auth_headers(token),
                      json={"name": "Primary", "team": "payments", "participants": [uid]})
    body = (await _poll(client, token, [_alert()])).json()
    incident_id = body["alerts"][0]["incident_id"]

    # Backdate assigned_at so MTTA is measurable.
    async with AsyncSessionLocal() as session:
        a = (await session.execute(select(IncidentAssignment).where(IncidentAssignment.incident_id == incident_id))).scalar_one()
        a.assigned_at = datetime.now(UTC) - timedelta(minutes=5)
        await session.commit()

    ack = await client.post(f"/v1/oncall/incidents/{incident_id}/acknowledge", headers=auth_headers(token), json={})
    assert ack.status_code == 200, ack.text
    assert ack.json()["state"] == "ACKNOWLEDGED"
    assert ack.json()["acknowledged_at"] is not None

    res = await client.post(f"/v1/oncall/incidents/{incident_id}/state", headers=auth_headers(token), json={"state": "RESOLVED"})
    assert res.status_code == 200 and res.json()["resolved_at"] is not None

    mtta = (await client.get("/v1/oncall/mtta", headers=auth_headers(token))).json()
    assert mtta["acknowledged_incidents"] >= 1
    assert mtta["organization_mtta_minutes"] is not None
    assert mtta["organization_mttr_minutes"] is not None


# ============================== escalation timing ========================== #
async def test_escalation_fires_after_threshold(client):
    me, tokens = await create_authenticated_user(client, email="oc7@e.com", username="onc7")
    token = tokens["access_token"]
    uid = me["id"]
    await _team_agent(client, token)
    await client.post("/v1/oncall/service-owners", headers=auth_headers(token),
                      json={"service_name": "checkout", "primary_owner_id": uid,
                            "secondary_owner_id": uid, "team": "payments"})
    await client.post("/v1/oncall/schedules", headers=auth_headers(token),
                      json={"name": "Primary", "team": "payments", "participants": [uid]})
    body = (await _poll(client, token, [_alert()])).json()
    incident_id = body["alerts"][0]["incident_id"]

    # Not yet due → no escalation.
    async with AsyncSessionLocal() as session:
        fired = await EscalationEngine(session).process_due()
    assert fired == 0

    # Backdate 25 minutes → default ladder (10m secondary, 20m primary) both fire.
    async with AsyncSessionLocal() as session:
        a = (await session.execute(select(IncidentAssignment).where(IncidentAssignment.incident_id == incident_id))).scalar_one()
        a.assigned_at = datetime.now(UTC) - timedelta(minutes=25)
        await session.commit()
    async with AsyncSessionLocal() as session:
        fired = await EscalationEngine(session).process_due()
    assert fired == 2

    a = (await client.get(f"/v1/oncall/incidents/{incident_id}/assignment", headers=auth_headers(token))).json()
    assert a["current_level"] == 2
    assert len(a["escalations"]) == 2


async def test_acknowledged_incident_does_not_escalate(client):
    me, tokens = await create_authenticated_user(client, email="oc8@e.com", username="onc8")
    token = tokens["access_token"]
    uid = me["id"]
    await _team_agent(client, token)
    await client.post("/v1/oncall/schedules", headers=auth_headers(token),
                      json={"name": "Primary", "team": "payments", "participants": [uid]})
    body = (await _poll(client, token, [_alert()])).json()
    incident_id = body["alerts"][0]["incident_id"]
    await client.post(f"/v1/oncall/incidents/{incident_id}/acknowledge", headers=auth_headers(token), json={})

    async with AsyncSessionLocal() as session:
        a = (await session.execute(select(IncidentAssignment).where(IncidentAssignment.incident_id == incident_id))).scalar_one()
        a.assigned_at = datetime.now(UTC) - timedelta(minutes=60)
        await session.commit()
    async with AsyncSessionLocal() as session:
        fired = await EscalationEngine(session).process_due()
    assert fired == 0  # acknowledged → escalation stops


# ============================== manual escalation trigger ================== #
async def test_manual_escalation_run_endpoint(client):
    _, tokens = await create_authenticated_user(client, email="oc9@e.com", username="onc9")
    token = tokens["access_token"]
    await _team_agent(client, token)
    await _poll(client, token, [_alert()])
    resp = await client.post("/v1/oncall/escalations/run", headers=auth_headers(token))
    assert resp.status_code == 200
    assert "escalations_fired" in resp.json()


# ============================== dashboard integration ===================== #
async def test_dashboard_includes_oncall_metrics(client):
    me, tokens = await create_authenticated_user(client, email="oc10@e.com", username="onc10")
    token = tokens["access_token"]
    uid = me["id"]
    await _team_agent(client, token)
    await client.post("/v1/oncall/schedules", headers=auth_headers(token),
                      json={"name": "Primary", "team": "payments", "participants": [uid]})
    await _poll(client, token, [_alert()])
    d = (await client.get("/v1/monitoring/dashboard", headers=auth_headers(token))).json()
    assert d["unacknowledged_incidents"] >= 1
    assert "mtta_minutes" in d
    assert any(c["user_id"] == uid for c in d["current_oncall"])


# ============================== audit + isolation ========================= #
async def test_audit_logging(client):
    me, tokens = await create_authenticated_user(client, email="oc11@e.com", username="onc11")
    token = tokens["access_token"]
    uid = me["id"]
    await _team_agent(client, token)
    await client.post("/v1/oncall/service-owners", headers=auth_headers(token),
                      json={"service_name": "checkout", "primary_owner_id": uid,
                            "secondary_owner_id": uid, "team": "payments"})
    await client.post("/v1/oncall/schedules", headers=auth_headers(token),
                      json={"name": "Primary", "team": "payments", "participants": [uid]})
    body = (await _poll(client, token, [_alert()])).json()
    incident_id = body["alerts"][0]["incident_id"]
    await client.post(f"/v1/oncall/incidents/{incident_id}/acknowledge", headers=auth_headers(token), json={})

    async with AsyncSessionLocal() as session:
        actions = {r.action for r in (await session.execute(select(AuditLog))).scalars().all()}
    for expected in ("service_owner_created", "oncall_schedule_created", "incident_assigned", "incident_acknowledged"):
        assert expected in actions, expected


async def test_tenant_isolation(client):
    me_a, tok_a = await create_authenticated_user(client, email="ocA@e.com", username="oncolA")
    _, tok_b = await create_authenticated_user(client, email="ocB@e.com", username="oncolB")
    await client.post("/v1/oncall/service-owners", headers=auth_headers(tok_a["access_token"]),
                      json={"service_name": "checkout", "primary_owner_id": me_a["id"]})
    # Org B cannot see org A's owners.
    lst_b = (await client.get("/v1/oncall/service-owners", headers=auth_headers(tok_b["access_token"]))).json()
    assert lst_b == []
