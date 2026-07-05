"""Tests for Sprint 46A - Reliability Maturity Score Engine.

Covers overall + category scoring, maturity-level mapping, strengths/weaknesses,
prioritized recommendations, trend reports, persistence, list/get, dashboard,
tenant isolation, and audit logging. All read-only.
"""

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.services.reliability_maturity import _level
from app.tests.conftest import auth_headers, create_authenticated_user

H = auth_headers
CATS = {"MONITORING", "INCIDENT_RESPONSE", "DEPLOYMENT", "SLO", "CAPACITY",
        "COST_OPTIMIZATION", "ONCALL"}


async def _team_agent(client, token):
    team = (await client.post("/v1/ai-teams", headers=H(token), json={"name": "Ops"})).json()
    await client.post("/v1/ai-team-agents", headers=H(token),
                      json={"team_id": team["id"], "name": "SRE", "role": "Ops", "instructions": "x",
                            "model": "claude-sonnet", "temperature": 0.2, "max_tokens": 300, "is_active": True})


async def _poll(client, token, name, service="checkout"):
    body = (await client.post("/v1/monitoring/poll", headers=H(token), json={"alerts": [
        {"provider": "PROMETHEUS", "alert_id": f"a-{name}", "alert_name": name,
         "severity": "CRITICAL", "service": service, "environment": "production"}]})).json()
    return body["alerts"][0]["incident_id"]


async def _analyze(client, token):
    return await client.post("/v1/reliability/analyze", headers=H(token))


# ============================== level mapping ============================ #
def test_level_mapping():
    assert _level(0) == "BEGINNER"
    assert _level(19) == "BEGINNER"
    assert _level(20) == "DEVELOPING"
    assert _level(39) == "DEVELOPING"
    assert _level(40) == "MATURE"
    assert _level(59) == "MATURE"
    assert _level(60) == "ADVANCED"
    assert _level(79) == "ADVANCED"
    assert _level(80) == "ELITE"
    assert _level(100) == "ELITE"


# ============================== scoring ================================== #
async def test_analyze_produces_full_assessment(client):
    _, t = await create_authenticated_user(client, email="rm1@e.com", username="rm1")
    token = t["access_token"]
    r = await _analyze(client, token)
    assert r.status_code == 201, r.text
    a = r.json()
    assert 0 <= a["overall_score"] <= 100
    assert a["maturity_level"] in {"BEGINNER", "DEVELOPING", "MATURE", "ADVANCED", "ELITE"}
    assert {c["category"] for c in a["categories"]} == CATS
    # weights sum to 1
    assert abs(sum(c["weight"] for c in a["categories"]) - 1.0) < 1e-6
    # each category has a level + detail
    for c in a["categories"]:
        assert c["maturity_level"] in {"BEGINNER", "DEVELOPING", "MATURE", "ADVANCED", "ELITE"}
        assert c["detail"]
    assert a["summary"]
    assert isinstance(a["recommendations"], list)


async def test_activity_raises_relevant_categories(client):
    _, t = await create_authenticated_user(client, email="rm2@e.com", username="rm2")
    token = t["access_token"]
    base = (await _analyze(client, token)).json()
    base_mon = next(c["score"] for c in base["categories"] if c["category"] == "MONITORING")

    # Generate monitoring activity across two providers + proactive incidents.
    await _team_agent(client, token)
    await client.post("/v1/monitoring/poll", headers=H(token), json={"alerts": [
        {"provider": "PROMETHEUS", "alert_id": "p1", "alert_name": "high cpu", "severity": "CRITICAL",
         "service": "checkout", "environment": "production"},
        {"provider": "DATADOG", "alert_id": "d1", "alert_name": "errors", "severity": "WARNING",
         "service": "api", "environment": "production"},
    ]})
    after = (await _analyze(client, token)).json()
    after_mon = next(c["score"] for c in after["categories"] if c["category"] == "MONITORING")
    assert after_mon > base_mon
    assert after_mon >= 60  # multi-provider + proactive incident


async def test_recommendations_prioritized_for_weak_categories(client):
    _, t = await create_authenticated_user(client, email="rm3@e.com", username="rm3")
    token = t["access_token"]
    a = (await _analyze(client, token)).json()
    recs = a["recommendations"]
    assert recs, "expected recommendations for a low-maturity org"
    # sorted by impact descending
    impacts = [r["impact"] for r in recs]
    assert impacts == sorted(impacts, reverse=True)
    assert all(r["priority"] in {"HIGH", "MEDIUM", "LOW"} for r in recs)
    # weak categories should surface as weaknesses
    assert isinstance(a["weaknesses"], list)


# ============================== trend ==================================== #
async def test_trend_reports(client):
    _, t = await create_authenticated_user(client, email="rm4@e.com", username="rm4")
    token = t["access_token"]
    await _analyze(client, token)
    await _team_agent(client, token)
    await _poll(client, token, "boom")
    second = (await _analyze(client, token)).json()
    # delta vs previous is recorded
    assert "delta_vs_previous" in second["details"]
    assert second["details"]["previous_overall_score"] is not None

    dash = (await client.get("/v1/reliability/dashboard", headers=H(token))).json()
    assert dash["assessments_count"] == 2
    assert len(dash["trend"]) == 2
    assert dash["latest"]["id"] == second["id"]
    assert dash["category_trends"]
    # each category trend has one point per assessment
    assert all(len(ct["points"]) == 2 for ct in dash["category_trends"])


# ============================== list / get =============================== #
async def test_list_and_get(client):
    _, t = await create_authenticated_user(client, email="rm5@e.com", username="rm5")
    token = t["access_token"]
    a = (await _analyze(client, token)).json()
    lst = (await client.get("/v1/reliability", headers=H(token))).json()
    assert len(lst) == 1 and lst[0]["id"] == a["id"]
    got = (await client.get(f"/v1/reliability/{a['id']}", headers=H(token))).json()
    assert got["id"] == a["id"] and {c["category"] for c in got["categories"]} == CATS
    assert (await client.get("/v1/reliability/nope", headers=H(token))).status_code == 404


# ============================== isolation ================================ #
async def test_tenant_isolation(client):
    _, t1 = await create_authenticated_user(client, email="rmA@e.com", username="rmA")
    _, t2 = await create_authenticated_user(client, email="rmB@e.com", username="rmB")
    tok1, tok2 = t1["access_token"], t2["access_token"]
    a = (await _analyze(client, tok1)).json()
    assert (await client.get("/v1/reliability", headers=H(tok2))).json() == []
    assert (await client.get(f"/v1/reliability/{a['id']}", headers=H(tok2))).status_code == 404
    d2 = (await client.get("/v1/reliability/dashboard", headers=H(tok2))).json()
    assert d2["assessments_count"] == 0 and d2["latest"] is None


# ============================== audit ==================================== #
async def test_audit_logging(client):
    me, t = await create_authenticated_user(client, email="rm6@e.com", username="rm6")
    token = t["access_token"]
    await _analyze(client, token)
    await client.get("/v1/reliability/dashboard", headers=H(token))
    async with AsyncSessionLocal() as session:
        actions = set(
            (await session.execute(select(AuditLog.action).where(AuditLog.user_id == me["id"]))).scalars().all()
        )
    assert {"reliability_assessment_created", "reliability_maturity_dashboard_viewed"} <= actions
