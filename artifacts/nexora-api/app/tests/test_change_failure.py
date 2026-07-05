"""Tests for Sprint 44C — Change Failure Prediction Engine.

Two layers:
* Pure, deterministic scoring units (no DB): factor weighting, probability
  scoring, risk-level thresholds, rollback/incident/SLO/blast-radius correlation,
  confidence, failure modes, mitigations.
* Read-only API surface: low-risk vs change-set probability, blast-radius
  correlation via the 44B dependency graph, SLO correlation via an active
  incident, persistence/get, dashboard, tenant isolation, audit, no-secret-leakage.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.models.oncall import IncidentAssignment
from app.services.change_failure import ChangeFailurePredictionService as CFP
from app.tests.conftest import auth_headers, create_authenticated_user


def _now():
    return datetime.now(UTC)


# ============================== pure scoring units ========================= #
def _factors(**kw):
    base = dict(risk_score=0, rollback_rate=None, success_rate=None, incident_count=0,
                mttr=None, burn_status="NORMAL", budget_pct=None, open_incidents=0,
                blast_level="LOW", tier=None)
    base.update(kw)
    return CFP._factors(**base)


def _points(factors, name):
    return sum(f.points for f in factors if f.factor == name)


def test_risk_level_thresholds():
    assert CFP._risk_level(0) == "LOW"
    assert CFP._risk_level(19) == "LOW"
    assert CFP._risk_level(20) == "MEDIUM"
    assert CFP._risk_level(39) == "MEDIUM"
    assert CFP._risk_level(40) == "HIGH"
    assert CFP._risk_level(64) == "HIGH"
    assert CFP._risk_level(65) == "CRITICAL"
    assert CFP._risk_level(100) == "CRITICAL"


def test_clean_signals_low_probability():
    factors = _factors(risk_score=0)
    prob = sum(f.points for f in factors)
    assert prob == 0
    assert CFP._risk_level(prob) == "LOW"


def test_deployment_risk_contributes_40_percent():
    assert _points(_factors(risk_score=100), "Deployment risk score (41D)") == 40
    assert _points(_factors(risk_score=50), "Deployment risk score (41D)") == 20


def test_rollback_correlation():
    assert _points(_factors(rollback_rate=2.0), "Rollback frequency") == 0
    assert _points(_factors(rollback_rate=10.0), "Rollback frequency") == 3
    assert _points(_factors(rollback_rate=20.0), "Rollback frequency") == 7
    assert _points(_factors(rollback_rate=40.0), "Rollback frequency") == 12


def test_success_rate_correlation():
    assert _points(_factors(success_rate=99.0), "Deployment success rate") == 0
    assert _points(_factors(success_rate=90.0), "Deployment success rate") == 2
    assert _points(_factors(success_rate=80.0), "Deployment success rate") == 6
    assert _points(_factors(success_rate=60.0), "Deployment success rate") == 12


def test_incident_correlation():
    assert _points(_factors(incident_count=0), "Incident history") == 0
    assert _points(_factors(incident_count=1), "Incident history") == 3
    assert _points(_factors(incident_count=3), "Incident history") == 6
    assert _points(_factors(incident_count=7), "Incident history") == 10
    assert _points(_factors(open_incidents=2), "Active incidents") == 8
    assert _points(_factors(open_incidents=10), "Active incidents") == 12  # capped


def test_slo_correlation():
    assert _points(_factors(burn_status="WARNING"), "SLO burn rate") == 6
    assert _points(_factors(burn_status="CRITICAL"), "SLO burn rate") == 12
    assert _points(_factors(budget_pct=10.0), "Error budget remaining") == 5
    assert _points(_factors(budget_pct=-5.0), "Error budget remaining") == 10


def test_blast_radius_correlation():
    assert _points(_factors(blast_level="MEDIUM"), "Blast radius (44B)") == 2
    assert _points(_factors(blast_level="HIGH"), "Blast radius (44B)") == 5
    assert _points(_factors(blast_level="CRITICAL"), "Blast radius (44B)") == 8


def test_tier_correlation():
    assert _points(_factors(tier="TIER_1"), "Service tier") == 5
    assert _points(_factors(tier="TIER_2"), "Service tier") == 2
    assert _points(_factors(tier="TIER_3"), "Service tier") == 0


def test_probability_clamped_and_monotonic():
    low = sum(f.points for f in _factors(risk_score=10))
    high = sum(f.points for f in _factors(
        risk_score=100, rollback_rate=50, success_rate=50, incident_count=9,
        mttr=300, burn_status="CRITICAL", budget_pct=-10, open_incidents=5,
        blast_level="CRITICAL", tier="TIER_1"))
    assert high > low
    assert int(max(0, min(100, round(high)))) == 100  # clamps at 100


def test_failure_modes_and_mitigations():
    req = type("R", (), {"has_database_migration": True, "has_infrastructure_changes": True,
                         "has_config_changes": True, "commit_count": 30, "changed_files": 60})()
    ins = type("I", (), {"rollback_rate": 25.0, "success_rate": 70.0})()
    modes = CFP._failure_modes(req, ins, "CRITICAL", -5.0, "CRITICAL")
    assert any("migration" in m.lower() for m in modes)
    assert any("infrastructure" in m.lower() for m in modes)
    assert any("misconfig" in m.lower() for m in modes)
    assert any("cascading" in m.lower() for m in modes)
    mits = CFP._mitigations(req, 80, "CRITICAL", -5.0, 2, "CRITICAL", ins, 3)
    assert any("canary" in m.lower() for m in mits)
    assert any("migration" in m.lower() for m in mits)
    assert any("monitoring" in m.lower() for m in mits)


def test_confidence_grows_with_data():
    assert CFP._confidence(0, False, 0) < CFP._confidence(10, True, 3)
    assert CFP._confidence(100, True, 5) <= 0.95


# ============================== API: helpers =============================== #
async def _predict(client, token, **body):
    return await client.post("/v1/change-failure-prediction/analyze",
                             headers=auth_headers(token), json=body)


async def _service(client, token, name, tier="TIER_2"):
    return (await client.post("/v1/services", headers=auth_headers(token),
                              json={"name": name, "tier": tier})).json()["id"]


async def _dep(client, token, src, tgt):
    return await client.post("/v1/service-dependencies", headers=auth_headers(token),
                             json={"source_service_id": src, "target_service_id": tgt})


async def _team_agent(client, token):
    team = (await client.post("/v1/ai-teams", headers=auth_headers(token), json={"name": "Ops"})).json()
    await client.post("/v1/ai-team-agents", headers=auth_headers(token),
                      json={"team_id": team["id"], "name": "SRE", "role": "Ops", "instructions": "x",
                            "model": "claude-sonnet", "temperature": 0.2, "max_tokens": 300, "is_active": True})


async def _poll_critical(client, token, service):
    return await client.post("/v1/monitoring/poll", headers=auth_headers(token), json={"alerts": [
        {"provider": "PROMETHEUS", "alert_id": "a1", "alert_name": "HighErrorRate",
         "severity": "CRITICAL", "service": service, "environment": "production"}]})


async def _age_assignment(service_name, minutes_ago):
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(IncidentAssignment).where(IncidentAssignment.service_name == service_name)
        )).scalars().all()
        for a in rows:
            a.assigned_at = _now() - timedelta(minutes=minutes_ago)
        await session.commit()


# ============================== API: integration ========================== #
async def test_low_risk_low_probability(client):
    _, tokens = await create_authenticated_user(client, email="cf1@e.com", username="cfp1")
    token = tokens["access_token"]
    r = await _predict(client, token, service=None, environment="staging")
    assert r.status_code == 201, r.text
    rep = r.json()
    assert rep["failure_probability"] < 20
    assert rep["risk_level"] == "LOW"
    assert rep["expected_blast_radius"] == "LOW"
    assert rep["prediction_id"]
    # the 41D risk factor is always present and explained
    assert any(f["factor"].startswith("Deployment risk") for f in rep["contributing_factors"])


async def test_change_set_raises_probability(client):
    _, tokens = await create_authenticated_user(client, email="cf2@e.com", username="cfp2")
    token = tokens["access_token"]
    low = (await _predict(client, token, service="api", environment="staging")).json()
    high = (await _predict(client, token, service="api", environment="production",
                           has_database_migration=True, has_infrastructure_changes=True,
                           has_config_changes=True, changed_files=60, commit_count=30,
                           production_only=True)).json()
    assert high["failure_probability"] > low["failure_probability"]
    assert high["risk_level"] in ("MEDIUM", "HIGH", "CRITICAL")
    modes = " ".join(high["likely_failure_modes"]).lower()
    assert "migration" in modes and "infrastructure" in modes
    assert any("canary" in m.lower() for m in high["recommended_mitigation_steps"])


async def test_blast_radius_correlation_via_graph(client):
    _, tokens = await create_authenticated_user(client, email="cf3@e.com", username="cfp3")
    token = tokens["access_token"]
    checkout = await _service(client, token, "checkout", tier="TIER_1")
    web = await _service(client, token, "web", tier="TIER_1")
    mobile = await _service(client, token, "mobile", tier="TIER_2")
    await _dep(client, token, web, checkout)   # web depends on checkout
    await _dep(client, token, mobile, web)      # mobile depends on web
    rep = (await _predict(client, token, service="checkout", environment="production")).json()
    assert rep["expected_blast_radius"] in ("HIGH", "CRITICAL")
    assert set(rep["signals"]["dependent_services"]) == {"web", "mobile"}
    assert any(f["factor"] == "Blast radius (44B)" for f in rep["contributing_factors"])


async def test_slo_correlation_via_active_incident(client):
    _, tokens = await create_authenticated_user(client, email="cf4@e.com", username="cfp4")
    token = tokens["access_token"]
    await _team_agent(client, token)
    await _service(client, token, "checkout", tier="TIER_1")
    await _poll_critical(client, token, "checkout")
    await _age_assignment("checkout", 60)  # long open outage → critical burn + over budget
    rep = (await _predict(client, token, service="checkout", environment="production")).json()
    names = {f["factor"] for f in rep["contributing_factors"]}
    assert "SLO burn rate" in names
    assert "Active incidents" in names
    assert rep["failure_probability"] >= 20


async def test_persisted_and_retrievable(client):
    _, tokens = await create_authenticated_user(client, email="cf5@e.com", username="cfp5")
    token = tokens["access_token"]
    rep = (await _predict(client, token, service="api", environment="production", version="v9.9.9")).json()
    pid = rep["prediction_id"]
    lst = (await client.get("/v1/change-failure-prediction", headers=auth_headers(token))).json()
    assert any(p["id"] == pid for p in lst)
    one = (await client.get(f"/v1/change-failure-prediction/{pid}", headers=auth_headers(token))).json()
    assert one["version"] == "v9.9.9"
    assert one["failure_probability"] == rep["failure_probability"]
    assert one["contributing_factors"]  # full report rehydrated


async def test_dashboard_counts(client):
    _, tokens = await create_authenticated_user(client, email="cf6@e.com", username="cfp6")
    token = tokens["access_token"]
    await _predict(client, token, service="a", environment="staging")
    await _predict(client, token, service="b", environment="production",
                   has_database_migration=True, changed_files=60, commit_count=30, production_only=True)
    dash = (await client.get("/v1/change-failure-prediction/dashboard", headers=auth_headers(token))).json()
    assert dash["total_predictions"] >= 2
    assert dash["average_failure_probability"] is not None
    assert (dash["low_count"] + dash["medium_count"] + dash["high_count"]
            + dash["critical_count"]) == dash["total_predictions"]


async def test_tenant_isolation(client):
    _, t1 = await create_authenticated_user(client, email="cfA@e.com", username="cfpA")
    _, t2 = await create_authenticated_user(client, email="cfB@e.com", username="cfpB")
    tok1, tok2 = t1["access_token"], t2["access_token"]
    rep = (await _predict(client, tok1, service="secret-svc")).json()
    pid = rep["prediction_id"]
    assert (await client.get("/v1/change-failure-prediction", headers=auth_headers(tok2))).json() == []
    assert (await client.get(f"/v1/change-failure-prediction/{pid}",
                             headers=auth_headers(tok2))).status_code == 404


async def test_audit_logging(client):
    me, tokens = await create_authenticated_user(client, email="cf7@e.com", username="cfp7")
    token = tokens["access_token"]
    await _predict(client, token, service="api")
    await client.get("/v1/change-failure-prediction/dashboard", headers=auth_headers(token))
    async with AsyncSessionLocal() as session:
        actions = set(
            (await session.execute(select(AuditLog.action).where(AuditLog.user_id == me["id"]))).scalars().all()
        )
    assert "change_failure_predicted" in actions
    assert "change_failure_dashboard_viewed" in actions


async def test_no_secret_leakage(client):
    _, tokens = await create_authenticated_user(client, email="cf8@e.com", username="cfp8")
    token = tokens["access_token"]
    rep = (await _predict(client, token, service="api", environment="production",
                          has_database_migration=True)).json()
    blob = str(rep).lower()
    for needle in ("password", "secret_key", "access_token", "bearer ", "authorization"):
        assert needle not in blob
