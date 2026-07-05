"""Tests for Sprint 46C - Executive Reliability Reporting Engine.

Covers report generation for each cadence (weekly/monthly/quarterly), required
sections + metrics, trend comparison vs the previous report, action plan
generation, list/get/404, PDF/HTML/Markdown export, tenant isolation, and audit
logging. Read-only.
"""

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.tests.conftest import auth_headers, create_authenticated_user

H = auth_headers


async def _service(client, token, name, tier="TIER_1"):
    return (await client.post("/v1/services", headers=H(token),
                              json={"name": name, "tier": tier, "owner_team": "core"})).json()


async def _slo(client, token, sid):
    return await client.post(f"/v1/services/{sid}/slos", headers=H(token),
                             json={"name": "av", "slo_type": "AVAILABILITY",
                                   "target_percentage": 99.9, "window_days": 30})


async def _gen(client, token, rtype="MONTHLY"):
    return await client.post("/v1/executive-reports/generate", headers=H(token),
                             json={"report_type": rtype})


# ============================== generation =============================== #
async def test_generate_weekly_monthly_quarterly(client):
    _, t = await create_authenticated_user(client, email="er1@e.com", username="er1")
    token = t["access_token"]
    await _service(client, token, "checkout")
    for rt, win in [("WEEKLY", 7), ("MONTHLY", 30), ("QUARTERLY", 90)]:
        r = await _gen(client, token, rt)
        assert r.status_code == 201, r.text
        rep = r.json()
        assert rep["report_type"] == rt
        assert rep["window_days"] == win
        assert 0 <= rep["reliability_score"] <= 100
        assert rep["score_grade"] in {"A", "B", "C", "D", "F"}


async def test_report_contains_required_sections(client):
    _, t = await create_authenticated_user(client, email="er2@e.com", username="er2")
    token = t["access_token"]
    a = await _service(client, token, "checkout")
    await _slo(client, token, a["id"])
    rep = (await _gen(client, token, "MONTHLY")).json()
    md = rep["content_markdown"]
    for section in ["Executive Summary", "Incident Summary", "Availability",
                    "MTTR", "MTTA", "SLO compliance", "Deployment Success",
                    "Cost Savings", "Capacity Forecast", "Reliability Score",
                    "Action Plan", "Trend Comparison"]:
        assert section in md, f"missing section: {section}"
    # metrics dict carries the key numbers
    m = rep["metrics"]
    for k in ["availability_30d", "mttr_minutes", "mtta_minutes", "slo_compliance_percentage",
              "deployment_success_rate", "potential_savings", "capacity_resources",
              "reliability_score", "score_grade"]:
        assert k in m
    assert rep["action_plan"]  # always at least one action (maintain)
    assert all("priority" in a for a in rep["action_plan"])


async def test_invalid_report_type(client):
    _, t = await create_authenticated_user(client, email="er3@e.com", username="er3")
    token = t["access_token"]
    r = await _gen(client, token, "DAILY")
    assert r.status_code == 400


# ============================== trend comparison ========================= #
async def test_trend_comparison_against_previous(client):
    _, t = await create_authenticated_user(client, email="er4@e.com", username="er4")
    token = t["access_token"]
    await _service(client, token, "checkout")
    first = (await _gen(client, token, "MONTHLY")).json()
    assert first["trend"]["previous_report_id"] is None
    assert "first report" in (first["trend"]["note"] or "").lower()
    second = (await _gen(client, token, "MONTHLY")).json()
    assert second["trend"]["previous_report_id"] == first["id"]
    assert second["trend"]["score_delta"] is not None
    assert isinstance(second["trend"]["deltas"], list)
    # different cadence still has no prior of its own type
    wk = (await _gen(client, token, "WEEKLY")).json()
    assert wk["trend"]["previous_report_id"] is None


# ============================== list / get / 404 ========================= #
async def test_list_get_and_filter(client):
    _, t = await create_authenticated_user(client, email="er5@e.com", username="er5")
    token = t["access_token"]
    await _service(client, token, "checkout")
    m1 = (await _gen(client, token, "MONTHLY")).json()
    await _gen(client, token, "WEEKLY")
    all_reports = (await client.get("/v1/executive-reports", headers=H(token))).json()
    assert len(all_reports) == 2
    monthly = (await client.get("/v1/executive-reports?report_type=MONTHLY", headers=H(token))).json()
    assert len(monthly) == 1 and monthly[0]["report_type"] == "MONTHLY"
    got = (await client.get(f"/v1/executive-reports/{m1['id']}", headers=H(token))).json()
    assert got["id"] == m1["id"]
    assert (await client.get("/v1/executive-reports/nope", headers=H(token))).status_code == 404


# ============================== exports ================================== #
async def test_exports_pdf_html_markdown(client):
    _, t = await create_authenticated_user(client, email="er6@e.com", username="er6")
    token = t["access_token"]
    await _service(client, token, "checkout")
    rep = (await _gen(client, token, "MONTHLY")).json()
    rid = rep["id"]
    pdf = await client.get(f"/v1/executive-reports/{rid}/export?format=pdf", headers=H(token))
    assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"
    html = await client.get(f"/v1/executive-reports/{rid}/export?format=html", headers=H(token))
    assert html.status_code == 200 and b"<html" in html.content.lower()
    md = await client.get(f"/v1/executive-reports/{rid}/export?format=markdown", headers=H(token))
    assert md.status_code == 200 and b"Executive Reliability Report" in md.content
    bad = await client.get(f"/v1/executive-reports/{rid}/export?format=xml", headers=H(token))
    assert bad.status_code == 400


# ============================== isolation ================================ #
async def test_tenant_isolation(client):
    _, t1 = await create_authenticated_user(client, email="erA@e.com", username="erA")
    _, t2 = await create_authenticated_user(client, email="erB@e.com", username="erB")
    tok1, tok2 = t1["access_token"], t2["access_token"]
    await _service(client, tok1, "checkout")
    rep = (await _gen(client, tok1, "MONTHLY")).json()
    assert (await client.get("/v1/executive-reports", headers=H(tok2))).json() == []
    assert (await client.get(f"/v1/executive-reports/{rep['id']}", headers=H(tok2))).status_code == 404
    assert (await client.get(f"/v1/executive-reports/{rep['id']}/export", headers=H(tok2))).status_code == 404


# ============================== audit ==================================== #
async def test_audit_logging(client):
    me, t = await create_authenticated_user(client, email="er7@e.com", username="er7")
    token = t["access_token"]
    rep = (await _gen(client, token, "MONTHLY")).json()
    await client.get(f"/v1/executive-reports/{rep['id']}/export?format=md", headers=H(token))
    async with AsyncSessionLocal() as session:
        actions = set(
            (await session.execute(select(AuditLog.action).where(AuditLog.user_id == me["id"]))).scalars().all()
        )
    assert {"executive_report_generated", "executive_report_exported"} <= actions
