"""Sprint 53B — Executive ROI Calculator tests.

Covers the engine formulas, API outputs (monthly/annual savings, ROI %,
payback period), the multi-year savings forecast, executive summary,
PDF/HTML/Markdown export, input validation, factor overrides, and audit
logging. The calculator is read-only and stateless (no business data touched).
"""

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.services.roi_calculator import (
    DEFAULT_INCIDENT_REDUCTION_PCT,
    DEFAULT_MTTR_REDUCTION_PCT,
    DEFAULT_PLATFORM_COST_PER_ENG_YEAR,
    RESPONDERS_PER_INCIDENT,
    WORKING_HOURS_PER_YEAR,
    ROICalculatorService,
    ROIInputs,
)
from app.tests.conftest import auth_headers, create_authenticated_user

H = auth_headers
BASE = "/v1/roi"

_SAMPLE = {
    "engineer_count": 50,
    "average_salary": 165000,
    "monthly_incidents": 40,
    "average_mttr_hours": 4,
    "deployments_per_month": 120,
    "oncall_burden_hours_per_week": 6,
}


async def _new_user(client, n: str):
    me, t = await create_authenticated_user(client, email=f"roi{n}@e.com", username=f"roi{n}")
    return me, t["access_token"]


# ----------------------------------------------------------------------- #
# Engine — formula correctness (no DB needed)
# ----------------------------------------------------------------------- #
def test_engine_formulas_match_spec():
    svc = ROICalculatorService()
    i = ROIInputs(**_SAMPLE)
    res = svc.calculate(i)

    hourly = 165000 / WORKING_HOURS_PER_YEAR
    inc_prevented = 40 * DEFAULT_INCIDENT_REDUCTION_PCT
    remaining = 40 - inc_prevented
    new_mttr = 4 * (1 - DEFAULT_MTTR_REDUCTION_PCT)
    inc_hours_saved = (40 * 4 - remaining * new_mttr) * RESPONDERS_PER_INCIDENT
    oncall_saved = 6 * 4.33 * 50 * 0.30
    deploy_saved = 120 * 0.5
    total_hours = inc_hours_saved + oncall_saved + deploy_saved
    labor = total_hours * hourly
    downtime_reduced = 40 * 4 - remaining * new_mttr
    downtime_savings = downtime_reduced * 5000.0
    monthly = labor + downtime_savings

    c = res["calculations"]
    assert abs(c["incident_hours_saved_month"] - round(inc_hours_saved, 2)) < 0.5
    assert abs(c["oncall_hours_saved_month"] - round(oncall_saved, 2)) < 0.5
    assert abs(c["deploy_hours_saved_month"] - deploy_saved) < 0.01
    assert abs(res["outputs"]["monthly_savings"] - round(monthly, 2)) < 1.0
    assert abs(res["outputs"]["annual_savings"] - round(monthly * 12, 2)) < 12.0


def test_engine_mttr_reduction_and_payback():
    svc = ROICalculatorService()
    res = svc.calculate(ROIInputs(**_SAMPLE))
    c = res["calculations"]
    # MTTR drops from 4h to 2.4h (40%) => 96 min reduction
    assert c["projected_mttr_hours"] == 2.4
    assert abs(c["mttr_reduction_minutes"] - 96.0) < 0.01
    # payback period positive and reasonable
    assert res["outputs"]["payback_period_months"] is not None
    assert res["outputs"]["payback_period_months"] > 0
    # ROI percentage computed against default platform cost
    platform = 50 * DEFAULT_PLATFORM_COST_PER_ENG_YEAR
    expected_roi = (res["outputs"]["annual_savings"] - platform) / platform * 100
    assert abs(res["outputs"]["roi_percentage"] - round(expected_roi, 1)) < 0.5


def test_engine_forecast_cumulative():
    svc = ROICalculatorService()
    res = svc.calculate(ROIInputs(**_SAMPLE))
    years = [r["year"] for r in res["forecast"]]
    assert years == [1, 2, 3, 5]
    monthly = res["outputs"]["monthly_savings"]
    row5 = next(r for r in res["forecast"] if r["year"] == 5)
    assert abs(row5["gross_savings"] - round(monthly * 60, 2)) < 60.0
    # net savings grow with horizon
    nets = [r["net_savings"] for r in res["forecast"]]
    assert nets == sorted(nets)


def test_engine_factor_overrides():
    svc = ROICalculatorService()
    base = svc.calculate(ROIInputs(**_SAMPLE))
    aggressive = svc.calculate(ROIInputs(**_SAMPLE, mttr_reduction_pct=0.8))
    assert aggressive["outputs"]["monthly_savings"] > base["outputs"]["monthly_savings"]
    assert aggressive["calculations"]["mttr_reduction_pct"] == 80.0


def test_engine_zero_incidents_no_negative():
    svc = ROICalculatorService()
    res = svc.calculate(ROIInputs(**{**_SAMPLE, "monthly_incidents": 0, "average_mttr_hours": 0}))
    assert res["calculations"]["incident_hours_saved_month"] == 0
    assert res["calculations"]["downtime_hours_reduced_month"] == 0
    # still savings from on-call + deployments
    assert res["outputs"]["monthly_savings"] > 0


def test_engine_validation_errors():
    svc = ROICalculatorService()
    for bad in (
        {**_SAMPLE, "engineer_count": 0},
        {**_SAMPLE, "average_salary": 0},
        {**_SAMPLE, "monthly_incidents": -1},
    ):
        try:
            svc.calculate(ROIInputs(**bad))
            assert False, f"expected ValidationError for {bad}"
        except Exception as exc:  # noqa: BLE001
            assert "must" in str(exc).lower()


def test_render_markdown_contains_sections():
    svc = ROICalculatorService()
    md = svc.render_markdown(svc.calculate(ROIInputs(**_SAMPLE)))
    for heading in (
        "Executive Summary", "Key Outcomes", "Time Saved",
        "MTTR Reduction", "Cost Reduction", "Downtime Reduction",
        "Savings Forecast", "Assumptions",
    ):
        assert heading in md


# ----------------------------------------------------------------------- #
# API — calculate / assumptions / report / export
# ----------------------------------------------------------------------- #
async def test_calculate_endpoint(client):
    _, token = await _new_user(client, "calc")
    r = await client.post(f"{BASE}/calculate", headers=H(token), json=_SAMPLE)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body["outputs"]) == {
        "monthly_savings", "annual_savings", "roi_percentage", "payback_period_months",
    }
    assert body["outputs"]["annual_savings"] > 0
    assert body["executive_summary"]
    assert len(body["forecast"]) == 4


async def test_assumptions_endpoint(client):
    _, token = await _new_user(client, "assum")
    r = await client.get(f"{BASE}/assumptions", headers=H(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mttr_reduction_pct"] == DEFAULT_MTTR_REDUCTION_PCT
    assert body["responders_per_incident"] == RESPONDERS_PER_INCIDENT


async def test_report_endpoint(client):
    _, token = await _new_user(client, "rep")
    r = await client.post(f"{BASE}/report", headers=H(token), json=_SAMPLE)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "# Executive ROI Report" in body["report_markdown"]
    assert body["outputs"]["monthly_savings"] > 0


async def test_export_pdf(client):
    _, token = await _new_user(client, "pdf")
    r = await client.post(f"{BASE}/export?format=pdf", headers=H(token), json=_SAMPLE)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-1.4")
    assert "roi-report.pdf" in r.headers["content-disposition"]


async def test_export_html(client):
    _, token = await _new_user(client, "html")
    r = await client.post(f"{BASE}/export?format=html", headers=H(token), json=_SAMPLE)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/html")
    assert b"Executive ROI Report" in r.content


async def test_export_unsupported_format(client):
    _, token = await _new_user(client, "bad")
    r = await client.post(f"{BASE}/export?format=xlsx", headers=H(token), json=_SAMPLE)
    assert r.status_code == 422, r.text


async def test_calculate_validation_via_api(client):
    _, token = await _new_user(client, "val")
    r = await client.post(f"{BASE}/calculate", headers=H(token),
                          json={**_SAMPLE, "engineer_count": 0})
    assert r.status_code == 422, r.text


async def test_calculate_requires_auth(client):
    r = await client.post(f"{BASE}/calculate", json=_SAMPLE)
    assert r.status_code in (401, 403)


async def test_calculate_writes_audit_log(client):
    _, token = await _new_user(client, "audit")
    r = await client.post(f"{BASE}/calculate", headers=H(token), json=_SAMPLE)
    assert r.status_code == 200, r.text
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(AuditLog).where(AuditLog.action == "roi_calculated")
        )).scalars().all()
    assert any(a.resource_type == "roi_calculation" for a in rows)
