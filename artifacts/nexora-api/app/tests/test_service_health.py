"""Tests for Sprint 42C — Service Health & SLO Intelligence.

Covers service catalog + SLO CRUD, availability calculation across 24h/7d/30d
windows, error-budget tracking, burn-rate classification (normal/warning/
critical), SLO violation prediction, per-SLO compliance (availability/error-rate/
latency), incident correlation, the health overview, tenant isolation, and audit
logging. All analytics are read-only.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.models.incident import MonitoringAlert
from app.models.oncall import IncidentAssignment
from app.tests.conftest import auth_headers, create_authenticated_user


def _now():
    return datetime.now(UTC)


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


async def _make_service(client, token, name="checkout", target=99.9, slo_type="AVAILABILITY", window=30):
    svc = (await client.post("/v1/services", headers=auth_headers(token),
                             json={"name": name, "owner_team": "payments", "tier": "TIER_1"})).json()
    await client.post(f"/v1/services/{svc['id']}/slos", headers=auth_headers(token),
                      json={"name": f"{name} SLO", "slo_type": slo_type,
                            "target_percentage": target, "window_days": window})
    return svc


async def _set_assignment_window(service_name, *, minutes_ago_start, duration_minutes=None):
    """Push the assignment's assigned_at into the past (and optionally resolve it)
    to simulate historical downtime for a service."""
    now = _now()
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(IncidentAssignment).where(IncidentAssignment.service_name == service_name)
        )).scalars().all()
        for a in rows:
            a.assigned_at = now - timedelta(minutes=minutes_ago_start)
            if duration_minutes is not None:
                a.resolved_at = a.assigned_at + timedelta(minutes=duration_minutes)
                a.state = "RESOLVED"
        await session.commit()


# ============================== catalog + SLO CRUD ========================= #
async def test_service_and_slo_crud(client):
    _, tokens = await create_authenticated_user(client, email="sh1@e.com", username="shealth1")
    token = tokens["access_token"]

    created = await client.post("/v1/services", headers=auth_headers(token),
                                json={"name": "api", "owner_team": "core", "tier": "TIER_1"})
    assert created.status_code == 201, created.text
    sid = created.json()["id"]

    lst = (await client.get("/v1/services", headers=auth_headers(token))).json()
    assert len(lst) == 1 and lst[0]["name"] == "api"

    upd = await client.patch(f"/v1/services/{sid}", headers=auth_headers(token),
                             json={"owner_team": "platform"})
    assert upd.status_code == 200 and upd.json()["owner_team"] == "platform"

    slo = await client.post(f"/v1/services/{sid}/slos", headers=auth_headers(token),
                            json={"name": "API Availability", "slo_type": "AVAILABILITY",
                                  "target_percentage": 99.95, "window_days": 30})
    assert slo.status_code == 201, slo.text
    slo_id = slo.json()["id"]
    assert slo.json()["target_percentage"] == 99.95

    slos = (await client.get(f"/v1/services/{sid}/slos", headers=auth_headers(token))).json()
    assert len(slos) == 1

    d = await client.delete(f"/v1/services/slos/{slo_id}", headers=auth_headers(token))
    assert d.status_code == 204
    assert len((await client.get(f"/v1/services/{sid}/slos", headers=auth_headers(token))).json()) == 0

    assert (await client.delete(f"/v1/services/{sid}", headers=auth_headers(token))).status_code == 204


async def test_invalid_slo_type_rejected(client):
    _, tokens = await create_authenticated_user(client, email="sh2@e.com", username="shealth2")
    token = tokens["access_token"]
    svc = (await client.post("/v1/services", headers=auth_headers(token),
                             json={"name": "api"})).json()
    r = await client.post(f"/v1/services/{svc['id']}/slos", headers=auth_headers(token),
                          json={"name": "bad", "slo_type": "NONSENSE", "target_percentage": 99.9})
    assert r.status_code == 400


# ============================== availability =============================== #
async def test_availability_healthy_when_no_incidents(client):
    _, tokens = await create_authenticated_user(client, email="sh3@e.com", username="shealth3")
    token = tokens["access_token"]
    svc = await _make_service(client, token, name="payments")
    report = (await client.get(f"/v1/services/{svc['id']}/health", headers=auth_headers(token))).json()
    a30 = next(w for w in report["availability"] if w["window"] == "30d")
    assert a30["availability_percentage"] == 100.0
    assert report["health_score"] == 100
    assert report["error_budget"]["remaining_minutes"] > 0
    assert report["prediction"]["will_breach"] is False


async def test_availability_windows_separate_24h_and_30d(client):
    _, tokens = await create_authenticated_user(client, email="sh4@e.com", username="shealth4")
    token = tokens["access_token"]
    await _team_agent(client, token)
    svc = await _make_service(client, token, name="checkout")
    await _poll(client, token, [_alert(service="checkout")])
    # 120-min outage that ended 10 days ago: inside 30d window, outside 24h.
    await _set_assignment_window("checkout", minutes_ago_start=10 * 24 * 60, duration_minutes=120)

    report = (await client.get(f"/v1/services/{svc['id']}/health", headers=auth_headers(token))).json()
    a24 = next(w for w in report["availability"] if w["window"] == "24h")
    a30 = next(w for w in report["availability"] if w["window"] == "30d")
    assert a24["availability_percentage"] == 100.0
    assert a30["downtime_minutes"] >= 119.0
    assert a30["availability_percentage"] < 100.0


# ============================== error budget + burn ======================== #
async def test_critical_burn_and_budget_exhaustion(client):
    _, tokens = await create_authenticated_user(client, email="sh5@e.com", username="shealth5")
    token = tokens["access_token"]
    await _team_agent(client, token)
    svc = await _make_service(client, token, name="checkout", target=99.9)
    await _poll(client, token, [_alert(service="checkout")])
    # Ongoing 60-min outage in the last 24h. Monthly budget @99.9% = 43.2 min.
    await _set_assignment_window("checkout", minutes_ago_start=60)

    report = (await client.get(f"/v1/services/{svc['id']}/health", headers=auth_headers(token))).json()
    eb = report["error_budget"]
    assert abs(eb["allowed_downtime_minutes"] - 43.2) < 0.5
    assert eb["consumed_minutes"] >= 59.0
    assert eb["remaining_minutes"] < 0  # over budget
    assert report["burn_rate"]["status"] == "CRITICAL"
    assert report["burn_rate"]["burn_rate"] > 10
    assert report["prediction"]["will_breach"] is True
    assert report["health_score"] < 90


async def test_warning_burn_rate(client):
    _, tokens = await create_authenticated_user(client, email="sh6@e.com", username="shealth6")
    token = tokens["access_token"]
    await _team_agent(client, token)
    svc = await _make_service(client, token, name="checkout", target=99.9)
    await _poll(client, token, [_alert(service="checkout")])
    # ~5 min outage -> burn ~3.5x (warning band 2x..10x).
    await _set_assignment_window("checkout", minutes_ago_start=5)

    report = (await client.get(f"/v1/services/{svc['id']}/health", headers=auth_headers(token))).json()
    assert report["burn_rate"]["status"] == "WARNING"
    assert 2 <= report["burn_rate"]["burn_rate"] < 10


async def test_prediction_message_format(client):
    _, tokens = await create_authenticated_user(client, email="sh7@e.com", username="shealth7")
    token = tokens["access_token"]
    await _team_agent(client, token)
    svc = await _make_service(client, token, name="checkout", target=99.9)
    await _poll(client, token, [_alert(service="checkout")])
    await _set_assignment_window("checkout", minutes_ago_start=3)
    report = (await client.get(f"/v1/services/{svc['id']}/health", headers=auth_headers(token))).json()
    msg = report["prediction"]["message"]
    assert "error budget" in msg and "days" in msg


# ============================== SLO compliance ============================= #
async def test_availability_slo_breached(client):
    _, tokens = await create_authenticated_user(client, email="sh8@e.com", username="shealth8")
    token = tokens["access_token"]
    await _team_agent(client, token)
    svc = await _make_service(client, token, name="checkout", target=99.9)
    await _poll(client, token, [_alert(service="checkout")])
    await _set_assignment_window("checkout", minutes_ago_start=200)  # heavy downtime
    report = (await client.get(f"/v1/services/{svc['id']}/health", headers=auth_headers(token))).json()
    avail_slo = next(s for s in report["slo_compliance"] if s["slo_type"] == "AVAILABILITY")
    assert avail_slo["status"] == "BREACHED"
    assert avail_slo["compliant"] is False


async def test_latency_slo_no_data(client):
    _, tokens = await create_authenticated_user(client, email="sh9@e.com", username="shealth9")
    token = tokens["access_token"]
    svc = (await client.post("/v1/services", headers=auth_headers(token), json={"name": "api"})).json()
    await client.post(f"/v1/services/{svc['id']}/slos", headers=auth_headers(token),
                      json={"name": "p99 latency", "slo_type": "LATENCY",
                            "target_percentage": 99.0, "latency_percentile": "P99", "threshold_ms": 250})
    report = (await client.get(f"/v1/services/{svc['id']}/health", headers=auth_headers(token))).json()
    lat = next(s for s in report["slo_compliance"] if s["slo_type"] == "LATENCY")
    assert lat["status"] == "NO_DATA"
    assert lat["observed_value"] is None
    assert lat["threshold_ms"] == 250


async def test_error_rate_slo_breached_with_alert_duration(client):
    _, tokens = await create_authenticated_user(client, email="sh10@e.com", username="shealth10")
    token = tokens["access_token"]
    await _team_agent(client, token)
    svc = await _make_service(client, token, name="checkout", target=99.99, slo_type="ERROR_RATE")
    await _poll(client, token, [_alert(service="checkout")])
    # Stretch the alert firing window to 30 min; budget @99.99% over 30d = 4.32 min.
    now = _now()
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(MonitoringAlert).where(MonitoringAlert.service == "checkout")
        )).scalars().all()
        for a in rows:
            a.first_seen_at = now - timedelta(minutes=30)
            a.last_seen_at = now
        await session.commit()
    report = (await client.get(f"/v1/services/{svc['id']}/health", headers=auth_headers(token))).json()
    er = next(s for s in report["slo_compliance"] if s["slo_type"] == "ERROR_RATE")
    assert er["compliant"] is False
    assert er["status"] == "BREACHED"


# ============================== correlation ================================ #
async def test_incident_and_alert_correlation(client):
    _, tokens = await create_authenticated_user(client, email="sh11@e.com", username="shealth11")
    token = tokens["access_token"]
    await _team_agent(client, token)
    svc = await _make_service(client, token, name="checkout")
    await _poll(client, token, [_alert(service="checkout")])
    report = (await client.get(f"/v1/services/{svc['id']}/health", headers=auth_headers(token))).json()
    assert len(report["correlated_incidents"]) >= 1
    assert len(report["correlated_alerts"]) >= 1
    assert report["correlated_alerts"][0]["alert_name"] == "HighErrorRate"


# ============================== overview =================================== #
async def test_health_overview(client):
    _, tokens = await create_authenticated_user(client, email="sh12@e.com", username="shealth12")
    token = tokens["access_token"]
    await _make_service(client, token, name="svc-a")
    await _make_service(client, token, name="svc-b")
    ov = (await client.get("/v1/services/health", headers=auth_headers(token))).json()
    assert len(ov["services"]) == 2
    assert ov["average_health_score"] is not None


# ============================== isolation ================================== #
async def test_tenant_isolation(client):
    _, t1 = await create_authenticated_user(client, email="shA@e.com", username="shealthA")
    _, t2 = await create_authenticated_user(client, email="shB@e.com", username="shealthB")
    tok1, tok2 = t1["access_token"], t2["access_token"]
    svc = (await client.post("/v1/services", headers=auth_headers(tok1), json={"name": "secret-svc"})).json()

    assert (await client.get(f"/v1/services/{svc['id']}", headers=auth_headers(tok2))).status_code == 404
    assert (await client.get(f"/v1/services/{svc['id']}/health", headers=auth_headers(tok2))).status_code in (403, 404)
    assert len((await client.get("/v1/services", headers=auth_headers(tok2))).json()) == 0


# ============================== audit ====================================== #
async def test_audit_logging(client):
    me, tokens = await create_authenticated_user(client, email="sh13@e.com", username="shealth13")
    token = tokens["access_token"]
    svc = await _make_service(client, token, name="audited")
    await client.get(f"/v1/services/{svc['id']}/health", headers=auth_headers(token))

    async with AsyncSessionLocal() as session:
        actions = set(
            (await session.execute(select(AuditLog.action).where(AuditLog.user_id == me["id"]))).scalars().all()
        )
    assert "service_created" in actions
    assert "service_slo_created" in actions
    assert "service_health_viewed" in actions
