"""Tests for Sprint 42D — Safe Deployment Intelligence.

Covers safety-score calculation, readiness state + readiness checks, canary /
strategy recommendations, blast-radius analysis, deployment-window guidance,
guardrail warnings, persistence + dashboard, tenant isolation, and audit logging.
All analytics are advisory and read-only.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
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


async def _poll_critical(client, token, service="checkout"):
    return await client.post("/v1/monitoring/poll", headers=auth_headers(token), json={"alerts": [
        {"provider": "PROMETHEUS", "alert_id": "a1", "alert_name": "HighErrorRate",
         "severity": "CRITICAL", "service": service, "environment": "production"}]})


async def _make_service(client, token, name, team="payments", tier="TIER_1"):
    return (await client.post("/v1/services", headers=auth_headers(token),
                              json={"name": name, "owner_team": team, "tier": tier})).json()


async def _analyze(client, token, **body):
    return await client.post("/v1/deployment-safety/analyze", headers=auth_headers(token), json=body)


async def _age_assignment(service_name, minutes_ago_start):
    now = _now()
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(IncidentAssignment).where(IncidentAssignment.service_name == service_name)
        )).scalars().all()
        for a in rows:
            a.assigned_at = now - timedelta(minutes=minutes_ago_start)
        await session.commit()


# ============================== low risk =================================== #
async def test_low_risk_full_rollout(client):
    _, tokens = await create_authenticated_user(client, email="ds1@e.com", username="dsafe1")
    token = tokens["access_token"]
    r = await _analyze(client, token, service=None, environment="staging")
    assert r.status_code == 200, r.text
    rep = r.json()
    assert rep["risk_score"] == 0
    assert rep["safety_score"] >= 90
    assert rep["readiness"] == "READY"
    assert rep["recommended_strategy"] == "FULL_ROLLOUT"
    assert rep["blast_radius"]["level"] == "LOW"
    assert rep["analysis_id"]


# ============================== change-set risk ============================ #
async def test_change_set_raises_risk_and_recommends_canary(client):
    _, tokens = await create_authenticated_user(client, email="ds2@e.com", username="dsafe2")
    token = tokens["access_token"]
    rep = (await _analyze(client, token, service="api", environment="production",
                          has_database_migration=True, has_infrastructure_changes=True,
                          production_only=True, changed_files=40)).json()
    assert rep["risk_score"] >= 50
    assert rep["recommended_strategy"] != "FULL_ROLLOUT"
    assert any("anary" in w for w in rep["warnings"])  # canary recommended


async def test_safety_score_decreases_with_risk(client):
    _, tokens = await create_authenticated_user(client, email="ds3@e.com", username="dsafe3")
    token = tokens["access_token"]
    low = (await _analyze(client, token, service=None, environment="staging")).json()
    high = (await _analyze(client, token, service="api", environment="production",
                           has_database_migration=True, has_infrastructure_changes=True,
                           changed_files=50, commit_count=30)).json()
    assert high["safety_score"] < low["safety_score"]


# ============================== blast radius =============================== #
async def test_blast_radius_tier1_with_dependents(client):
    _, tokens = await create_authenticated_user(client, email="ds4@e.com", username="dsafe4")
    token = tokens["access_token"]
    await _make_service(client, token, "checkout", team="payments", tier="TIER_1")
    await _make_service(client, token, "ledger", team="payments", tier="TIER_2")
    await _make_service(client, token, "wallet", team="payments", tier="TIER_2")
    rep = (await _analyze(client, token, service="checkout", environment="production")).json()
    assert rep["blast_radius"]["level"] == "CRITICAL"
    assert set(rep["blast_radius"]["dependent_services"]) == {"ledger", "wallet"}
    assert any("Tier-1" in i for i in rep["blast_radius"]["customer_impact"])


# ============================== readiness ================================== #
async def test_not_ready_with_critical_burn_and_open_incident(client):
    _, tokens = await create_authenticated_user(client, email="ds5@e.com", username="dsafe5")
    token = tokens["access_token"]
    await _team_agent(client, token)
    await _make_service(client, token, "checkout", team="payments", tier="TIER_1")
    await _poll_critical(client, token, "checkout")
    await _age_assignment("checkout", 60)  # 60 min open outage -> critical burn + over budget

    rep = (await _analyze(client, token, service="checkout", environment="production")).json()
    assert rep["readiness"] == "NOT_READY"
    assert any("NOT READY" in w for w in rep["warnings"])
    assert any("error budget" in w.lower() for w in rep["warnings"])
    # critical burn + open incident + not-ready shifts strategy to the safest tiers.
    assert rep["recommended_strategy"] in ("CANARY_5", "BLUE_GREEN")


async def test_readiness_checks_present(client):
    _, tokens = await create_authenticated_user(client, email="ds6@e.com", username="dsafe6")
    token = tokens["access_token"]
    rep = (await _analyze(client, token, service="api")).json()
    names = {c["name"] for c in rep["readiness_checks"]}
    assert {"Active incidents", "Open remediation actions", "Error budget",
            "Burn rate", "Service health"} <= names


# ============================== deployment window ========================== #
async def test_deployment_window_defers_during_incident(client):
    _, tokens = await create_authenticated_user(client, email="ds7@e.com", username="dsafe7")
    token = tokens["access_token"]
    await _team_agent(client, token)
    await _make_service(client, token, "checkout", team="payments", tier="TIER_1")
    await _poll_critical(client, token, "checkout")
    await _age_assignment("checkout", 60)
    rep = (await _analyze(client, token, service="checkout", environment="production")).json()
    assert "Defer" in rep["recommended_window"]
    assert any("incident" in a.lower() for a in rep["avoid_windows"])


async def test_window_recommends_offpeak_when_healthy(client):
    _, tokens = await create_authenticated_user(client, email="ds8@e.com", username="dsafe8")
    token = tokens["access_token"]
    rep = (await _analyze(client, token, service="api", environment="production")).json()
    assert "maintenance window" in rep["recommended_window"].lower()
    assert any("peak" in a.lower() for a in rep["avoid_windows"])


# ============================== persistence + dashboard ==================== #
async def test_analysis_persisted_and_retrievable(client):
    _, tokens = await create_authenticated_user(client, email="ds9@e.com", username="dsafe9")
    token = tokens["access_token"]
    rep = (await _analyze(client, token, service="api", environment="production", version="v1.2.3")).json()
    aid = rep["analysis_id"]
    lst = (await client.get("/v1/deployment-safety/analyses", headers=auth_headers(token))).json()
    assert any(a["id"] == aid for a in lst)
    one = (await client.get(f"/v1/deployment-safety/analyses/{aid}", headers=auth_headers(token))).json()
    assert one["service"] == "api" and one["version"] == "v1.2.3"
    assert one["safety_score"] == rep["safety_score"]


async def test_dashboard_counts(client):
    _, tokens = await create_authenticated_user(client, email="ds10@e.com", username="dsafe10")
    token = tokens["access_token"]
    await _analyze(client, token, service="a", environment="staging")
    await _analyze(client, token, service="b", environment="production",
                   has_database_migration=True, changed_files=50)
    dash = (await client.get("/v1/deployment-safety/dashboard", headers=auth_headers(token))).json()
    assert dash["total_analyses"] >= 2
    assert dash["average_safety_score"] is not None
    assert dash["ready_count"] + dash["at_risk_count"] + dash["not_ready_count"] == dash["total_analyses"]


# ============================== isolation ================================== #
async def test_tenant_isolation(client):
    _, t1 = await create_authenticated_user(client, email="dsA@e.com", username="dsafeA")
    _, t2 = await create_authenticated_user(client, email="dsB@e.com", username="dsafeB")
    tok1, tok2 = t1["access_token"], t2["access_token"]
    rep = (await _analyze(client, tok1, service="secret")).json()
    aid = rep["analysis_id"]
    assert len((await client.get("/v1/deployment-safety/analyses", headers=auth_headers(tok2))).json()) == 0
    assert (await client.get(f"/v1/deployment-safety/analyses/{aid}", headers=auth_headers(tok2))).status_code == 404


# ============================== audit ====================================== #
async def test_audit_logging(client):
    me, tokens = await create_authenticated_user(client, email="ds11@e.com", username="dsafe11")
    token = tokens["access_token"]
    await _analyze(client, token, service="api")
    await client.get("/v1/deployment-safety/dashboard", headers=auth_headers(token))
    async with AsyncSessionLocal() as session:
        actions = set(
            (await session.execute(select(AuditLog.action).where(AuditLog.user_id == me["id"]))).scalars().all()
        )
    assert "deployment_safety_analyzed" in actions
    assert "deployment_safety_dashboard_viewed" in actions
