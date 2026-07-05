"""Tests for Sprint 45B - Executive Reliability Dashboard.

Covers reliability-score calculation + breakdown, trend generation (7/30/90d),
org/team/service views, executive summary, export (pdf/html/markdown), input
validation, tenant isolation, and audit logging. All read-only.
"""

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.tests.conftest import auth_headers, create_authenticated_user

H = auth_headers


async def _team_agent(client, token):
    team = (await client.post("/v1/ai-teams", headers=H(token), json={"name": "Ops"})).json()
    await client.post("/v1/ai-team-agents", headers=H(token),
                      json={"team_id": team["id"], "name": "SRE", "role": "Ops", "instructions": "x",
                            "model": "claude-sonnet", "temperature": 0.2, "max_tokens": 300, "is_active": True})


async def _poll(client, token, name, service):
    body = (await client.post("/v1/monitoring/poll", headers=H(token), json={"alerts": [
        {"provider": "PROMETHEUS", "alert_id": f"a-{name}-{service}", "alert_name": name,
         "severity": "CRITICAL", "service": service, "environment": "production"}]})).json()
    return body["alerts"][0]["incident_id"]


async def _service(client, token, name, team="core", tier="TIER_1"):
    return (await client.post("/v1/services", headers=H(token),
                              json={"name": name, "tier": tier, "owner_team": team})).json()


async def _dash(client, token, **q):
    qs = "&".join(f"{k}={v}" for k, v in q.items())
    return await client.get(f"/v1/reliability-dashboard{('?' + qs) if qs else ''}", headers=H(token))


# ============================== score ==================================== #
async def test_empty_org_scores_high(client):
    _, t = await create_authenticated_user(client, email="rd1@e.com", username="rd1")
    token = t["access_token"]
    r = await _dash(client, token)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["scope"] == "organization"
    assert d["reliability_score"] == 100 and d["score_grade"] == "A"
    assert len(d["score_breakdown"]) == 7
    assert abs(sum(c["weight"] for c in d["score_breakdown"]) - 1.0) < 1e-6
    assert abs(sum(c["points"] for c in d["score_breakdown"]) - 100.0) < 0.5


async def test_incidents_lower_score(client):
    _, t = await create_authenticated_user(client, email="rd2@e.com", username="rd2")
    token = t["access_token"]
    await _team_agent(client, token)
    for i in range(5):
        await _poll(client, token, f"down{i}", "checkout")
    d = (await _dash(client, token, window=30)).json()
    assert d["metrics"]["total_incidents"] >= 5
    assert d["reliability_score"] < 100
    inc = next(c for c in d["score_breakdown"] if c["name"] == "Incident frequency")
    assert inc["score"] < 100


# ============================== trends =================================== #
async def test_trend_buckets(client):
    _, t = await create_authenticated_user(client, email="rd3@e.com", username="rd3")
    token = t["access_token"]
    await _team_agent(client, token)
    await _poll(client, token, "boom", "api")
    d = (await _dash(client, token)).json()
    assert d["trends_7d"]["window_days"] == 7 and len(d["trends_7d"]["buckets"]) == 7
    assert d["trends_30d"]["window_days"] == 30 and len(d["trends_30d"]["buckets"]) == 10
    assert d["trends_90d"]["window_days"] == 90 and len(d["trends_90d"]["buckets"]) == 10
    # the incident lands in the latest bucket of the 7d series
    assert d["trends_7d"]["buckets"][-1]["incidents"] >= 1


# ============================== views ==================================== #
async def test_team_and_service_views(client):
    _, t = await create_authenticated_user(client, email="rd4@e.com", username="rd4")
    token = t["access_token"]
    await _service(client, token, "checkout", team="payments-team")
    await _service(client, token, "billing", team="payments-team")
    await _service(client, token, "search", team="search-team")

    org = (await _dash(client, token)).json()
    assert org["metrics"]["services_total"] == 3

    team = (await _dash(client, token, scope="team", value="payments-team")).json()
    assert team["scope"] == "team" and team["metrics"]["services_total"] == 2

    svc = (await _dash(client, token, scope="service", value="checkout")).json()
    assert svc["scope"] == "service" and svc["metrics"]["services_total"] == 1


async def test_validation(client):
    _, t = await create_authenticated_user(client, email="rd5@e.com", username="rd5")
    token = t["access_token"]
    assert (await _dash(client, token, scope="team")).status_code == 400
    assert (await _dash(client, token, scope="bogus")).status_code == 400
    # invalid window coerces to 30
    d = (await _dash(client, token, window=999)).json()
    assert d["window_days"] == 30


# ============================== summary ================================== #
async def test_summary(client):
    _, t = await create_authenticated_user(client, email="rd6@e.com", username="rd6")
    token = t["access_token"]
    r = await client.get("/v1/reliability-dashboard/summary", headers=H(token))
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["summary"] and "reliability_score" in s
    assert isinstance(s["recommendations"], list) and s["recommendations"]


# ============================== export =================================== #
async def test_export_pdf_html_markdown(client):
    _, t = await create_authenticated_user(client, email="rd7@e.com", username="rd7")
    token = t["access_token"]
    pdf = await client.get("/v1/reliability-dashboard/export?format=pdf", headers=H(token))
    assert pdf.status_code == 200
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content[:5] == b"%PDF-"

    html = await client.get("/v1/reliability-dashboard/export?format=html", headers=H(token))
    assert html.status_code == 200 and b"<html" in html.content.lower()

    md = await client.get("/v1/reliability-dashboard/export?format=markdown", headers=H(token))
    assert md.status_code == 200 and b"# Executive Reliability Report" in md.content

    bad = await client.get("/v1/reliability-dashboard/export?format=xml", headers=H(token))
    assert bad.status_code == 400


# ============================== isolation ================================ #
async def test_tenant_isolation(client):
    _, t1 = await create_authenticated_user(client, email="rdA@e.com", username="rdA")
    _, t2 = await create_authenticated_user(client, email="rdB@e.com", username="rdB")
    tok1, tok2 = t1["access_token"], t2["access_token"]
    await _team_agent(client, tok1)
    for i in range(3):
        await _poll(client, tok1, f"x{i}", "checkout")
    d1 = (await _dash(client, tok1)).json()
    d2 = (await _dash(client, tok2)).json()
    assert d1["metrics"]["total_incidents"] >= 3
    assert d2["metrics"]["total_incidents"] == 0


# ============================== audit ==================================== #
async def test_audit_logging(client):
    me, t = await create_authenticated_user(client, email="rd8@e.com", username="rd8")
    token = t["access_token"]
    await _dash(client, token)
    await client.get("/v1/reliability-dashboard/summary", headers=H(token))
    await client.get("/v1/reliability-dashboard/export?format=pdf", headers=H(token))
    async with AsyncSessionLocal() as session:
        actions = set(
            (await session.execute(select(AuditLog.action).where(AuditLog.user_id == me["id"]))).scalars().all()
        )
    assert {"reliability_dashboard_viewed", "reliability_summary_generated",
            "reliability_dashboard_exported"} <= actions
