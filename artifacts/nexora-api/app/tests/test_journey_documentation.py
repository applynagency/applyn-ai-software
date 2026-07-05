"""Sprint 56D.3 — End-to-End Customer Journey Documentation tests.

Verifies the four end-to-end journeys are complete, self-service walkthroughs:
each stage carries navigation, screenshot, expected screen, what-happens-
internally, expected outcome, common issues, and recovery steps; each journey
has a diagram; and journey manuals export as PDF / HTML / Markdown.
"""

import pytest

from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
)

BASE = "/v1/customer-success"

# Required journeys and their ordered stage titles (from the sprint brief).
JOURNEY_STAGES = {
    "infrastructure-onboarding": [
        "Connect Provider", "Discovery", "Service Mapping",
        "Dependency Discovery", "SLO Creation", "Monitoring Setup",
    ],
    "incident-management": [
        "Alert", "Incident", "Timeline", "Change Intelligence",
        "Recommendations", "Remediation", "Postmortem",
    ],
    "safe-deployment": [
        "Deployment Risk", "Deployment Safety",
        "Change Failure Prediction", "Deployment Review",
    ],
    "executive-reporting": [
        "SLO", "Capacity", "Cost", "Reliability Dashboard", "Executive Report",
    ],
}

STAGE_FIELDS = (
    "navigation", "route", "expected_screen", "internal",
    "expected_outcome", "common_issues", "recovery_steps", "screenshot",
)


async def _org_token(client) -> str:
    _, tokens = await create_authenticated_user(
        client, email="journey@example.com", username="journeyuser"
    )
    org = await create_organization(client, tokens["access_token"], name="Journey Org")
    return org["context"]["access_token"]


@pytest.mark.asyncio
async def test_required_journeys_have_expected_stages(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/journeys", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    journeys = {j["key"]: j for j in resp.json()["items"]}
    for key, titles in JOURNEY_STAGES.items():
        assert key in journeys, f"missing journey {key}"
        j = journeys[key]
        assert j["diagram"].strip().startswith("graph"), key
        assert [s["title"] for s in j["stages"]] == titles, key


@pytest.mark.asyncio
async def test_every_stage_is_self_service_complete(client):
    token = await _org_token(client)
    for key in JOURNEY_STAGES:
        resp = await client.get(f"{BASE}/journeys/{key}", headers=auth_headers(token))
        assert resp.status_code == 200, resp.text
        j = resp.json()
        assert j["diagram"].strip(), key
        for s in j["stages"]:
            for field in STAGE_FIELDS:
                assert s.get(field) not in (None, "", []), (key, s["order"], field)
            assert len(s["navigation"]) >= 1, (key, s["order"])
            assert len(s["expected_screen"]) >= 1, (key, s["order"])
            assert len(s["common_issues"]) >= 1, (key, s["order"])
            assert len(s["recovery_steps"]) >= 1, (key, s["order"])
            assert s["internal"].strip(), (key, s["order"])


@pytest.mark.asyncio
async def test_journey_diagrams_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/journey-diagrams", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 4
    keys = {d["key"] for d in body["items"]}
    assert set(JOURNEY_STAGES) <= keys
    for d in body["items"]:
        assert d["diagram"].strip().startswith("graph"), d["key"]


@pytest.mark.asyncio
async def test_journey_manuals_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/journey-manuals", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 4
    for m in body["items"]:
        md = m["markdown"]
        assert "## Step-by-step walkthrough" in md, m["key"]
        assert "What happens internally" in md, m["key"]
        assert "Recovery steps" in md, m["key"]
        assert "Navigation" in md, m["key"]


@pytest.mark.asyncio
async def test_single_journey_manual(client):
    token = await _org_token(client)
    resp = await client.get(
        f"{BASE}/journeys/incident-management/manual", headers=auth_headers(token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["key"] == "incident-management"
    # All seven stages present in the manual.
    for title in JOURNEY_STAGES["incident-management"]:
        assert title in body["markdown"]


@pytest.mark.asyncio
async def test_journey_exports_pdf_html_markdown(client):
    token = await _org_token(client)
    # PDF
    pdf = await client.get(
        f"{BASE}/journeys/safe-deployment/export?format=pdf", headers=auth_headers(token)
    )
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content[:5] == b"%PDF-"
    # HTML
    html = await client.get(
        f"{BASE}/journeys/safe-deployment/export?format=html", headers=auth_headers(token)
    )
    assert html.status_code == 200
    assert "<!doctype html>" in html.text.lower()
    # Markdown
    md = await client.get(
        f"{BASE}/journeys/executive-reporting/export?format=markdown",
        headers=auth_headers(token),
    )
    assert md.status_code == 200
    assert "# Executive Reporting" in md.text


@pytest.mark.asyncio
async def test_unknown_journey_manual_returns_404(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/journeys/not-real/manual", headers=auth_headers(token))
    assert resp.status_code == 404
