"""Sprint 53D - Sales & Demo Enablement tests.

Covers the six enablement surfaces:
  1. Demo Recording Library (+ filters)
  2. Product Videos (+ category filter)
  3. Demo Scenario Launcher (5 built-in scenarios)
  4. Competitive Comparison (Datadog, New Relic, PagerDuty, Dynatrace, Resolve.ai)
  5. Value Proposition Generator (CTO, VP Eng, DevOps Mgr, Startup Founder)
  6. Proposal Generator (Proposal / Scope / Pricing) + pricing math
Plus PDF/HTML/Markdown exports, validation errors, audit logging, and auth.
Read-only.
"""

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.tests.conftest import auth_headers, create_authenticated_user

H = auth_headers
BASE = "/v1/sales"

_COMPETITORS = {"DATADOG", "NEW_RELIC", "PAGERDUTY", "DYNATRACE", "RESOLVE_AI"}
_PERSONAS = {"CTO", "VP_ENGINEERING", "DEVOPS_MANAGER", "STARTUP_FOUNDER"}


async def _user(client, n):
    _, t = await create_authenticated_user(client, email=f"se{n}@e.com", username=f"se{n}")
    return t["access_token"]


# ============================ 1. recordings ============================= #
async def test_demo_recordings(client):
    token = await _user(client, "rec")
    r = await client.get(f"{BASE}/demo-recordings", headers=H(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] >= 5
    assert body["curated"]
    assert all("url" in rec for rec in body["curated"])


async def test_demo_recordings_filter(client):
    token = await _user(client, "recf")
    r = await client.get(f"{BASE}/demo-recordings?scenario=CHECKOUT_OUTAGE", headers=H(token))
    assert r.status_code == 200
    assert all(rec["scenario"] == "CHECKOUT_OUTAGE" for rec in r.json()["curated"])


# ============================ 2. product videos ========================= #
async def test_product_videos(client):
    token = await _user(client, "vid")
    r = await client.get(f"{BASE}/product-videos", headers=H(token))
    assert r.status_code == 200
    assert r.json()["total"] >= 5

    r = await client.get(f"{BASE}/product-videos?category=INCIDENTS", headers=H(token))
    assert r.status_code == 200
    assert all(v["category"] == "INCIDENTS" for v in r.json()["videos"])


# ============================ 3. launcher =============================== #
async def test_scenario_launcher(client):
    token = await _user(client, "launch")
    r = await client.get(f"{BASE}/scenario-launcher", headers=H(token))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 5
    for s in body["scenarios"]:
        assert s["step_count"] >= 1
        assert "run_endpoint" in s["launch"]


# ============================ 4. comparison ============================= #
async def test_comparison_all(client):
    token = await _user(client, "cmp")
    r = await client.get(f"{BASE}/competitive-comparison", headers=H(token))
    assert r.status_code == 200
    body = r.json()
    assert set(body["competitor_order"]) == _COMPETITORS
    assert set(body["competitors"].keys()) == _COMPETITORS
    assert body["features"]
    # every feature row scores nexora + each competitor
    for f in body["features"]:
        assert "nexora" in f
        for c in _COMPETITORS:
            assert c in f


async def test_comparison_single_competitor(client):
    token = await _user(client, "cmp1")
    r = await client.get(f"{BASE}/competitive-comparison?competitor=DATADOG", headers=H(token))
    assert r.status_code == 200
    assert r.json()["competitor_order"] == ["DATADOG"]


async def test_comparison_unknown_competitor(client):
    token = await _user(client, "cmpx")
    r = await client.get(f"{BASE}/competitive-comparison?competitor=SPLUNK", headers=H(token))
    assert r.status_code == 400


async def test_comparison_export(client):
    token = await _user(client, "cmpe")
    r = await client.get(f"{BASE}/competitive-comparison/export?format=pdf", headers=H(token))
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF-1.4")

    r = await client.get(f"{BASE}/competitive-comparison/export?format=markdown", headers=H(token))
    assert r.status_code == 200
    assert b"Competitive Comparison" in r.content


# ============================ 5. value prop ============================= #
async def test_personas_list(client):
    token = await _user(client, "per")
    r = await client.get(f"{BASE}/personas", headers=H(token))
    assert r.status_code == 200
    keys = {p["key"] for p in r.json()["personas"]}
    assert keys == _PERSONAS


async def test_generate_all_four_pitches(client):
    token = await _user(client, "pitch")
    for persona in _PERSONAS:
        r = await client.post(f"{BASE}/value-proposition", headers=H(token),
                              json={"persona": persona, "company_name": "Acme"})
        assert r.status_code == 200, r.text
        vp = r.json()
        assert vp["persona"] == persona
        assert vp["pains"] and vp["gains"] and vp["proof_points"]
        assert vp["call_to_action"]


async def test_value_proposition_unknown_persona(client):
    token = await _user(client, "pitchx")
    r = await client.post(f"{BASE}/value-proposition", headers=H(token),
                          json={"persona": "INTERN"})
    assert r.status_code == 400


async def test_value_proposition_export(client):
    token = await _user(client, "pitche")
    r = await client.post(f"{BASE}/value-proposition/export?format=html", headers=H(token),
                          json={"persona": "CTO", "company_name": "Acme"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert b"Pitch" in r.content


# ============================ 6. proposal ============================== #
async def test_pricing_catalog(client):
    token = await _user(client, "price")
    r = await client.get(f"{BASE}/pricing", headers=H(token))
    assert r.status_code == 200
    keys = {t["key"] for t in r.json()["tiers"]}
    assert keys == {"STARTER", "GROWTH", "SCALE", "ENTERPRISE"}


async def test_generate_proposal_with_pricing_math(client):
    token = await _user(client, "prop")
    r = await client.post(f"{BASE}/proposal", headers=H(token),
                          json={"company_name": "Acme Corp", "engineer_count": 40,
                                "tier": "GROWTH", "term_months": 12})
    assert r.status_code == 200, r.text
    body = r.json()
    pr = body["pricing"]
    assert pr["tier"] == "GROWTH"
    assert pr["monthly_total"] == 49 * 40
    assert pr["annual_total"] == 49 * 40 * 12
    assert pr["term_total"] == 49 * 40 * 12
    assert body["scope"]["phases"]
    assert body["proposal"]["executive_summary"]


async def test_proposal_recommends_tier_when_omitted(client):
    token = await _user(client, "proprec")
    r = await client.post(f"{BASE}/proposal", headers=H(token),
                          json={"company_name": "Acme", "engineer_count": 100})
    assert r.status_code == 200
    # 100 engineers falls into SCALE (51-250)
    assert r.json()["pricing"]["tier"] == "SCALE"


async def test_proposal_validation(client):
    token = await _user(client, "propv")
    r = await client.post(f"{BASE}/proposal", headers=H(token),
                          json={"company_name": "Acme", "engineer_count": 0})
    assert r.status_code == 422  # pydantic gt=0


async def test_proposal_exports_three_documents(client):
    token = await _user(client, "prope")
    payload = {"company_name": "Acme Corp", "engineer_count": 40, "tier": "GROWTH"}
    for doc, marker in [("proposal", b"Proposal"), ("scope", b"Scope Document"),
                        ("pricing", b"Pricing Sheet")]:
        r = await client.post(f"{BASE}/proposal/export?document={doc}&format=markdown",
                              headers=H(token), json=payload)
        assert r.status_code == 200, r.text
        assert marker in r.content

    # PDF export of the proposal
    r = await client.post(f"{BASE}/proposal/export?document=proposal&format=pdf",
                          headers=H(token), json=payload)
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF-1.4")


async def test_proposal_export_unknown_document(client):
    token = await _user(client, "propx")
    r = await client.post(f"{BASE}/proposal/export?document=invoice",
                          headers=H(token),
                          json={"company_name": "Acme", "engineer_count": 10})
    assert r.status_code == 400


# ============================ audit / auth ============================= #
async def test_proposal_writes_audit_log(client):
    token = await _user(client, "audit")
    await client.post(f"{BASE}/proposal", headers=H(token),
                      json={"company_name": "Acme", "engineer_count": 10})
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(AuditLog).where(AuditLog.action == "proposal_generated")
        )).scalars().all()
    assert any(a.resource_type == "sales_enablement" for a in rows)


async def test_requires_auth(client):
    r = await client.get(f"{BASE}/personas")
    assert r.status_code in (401, 403)
