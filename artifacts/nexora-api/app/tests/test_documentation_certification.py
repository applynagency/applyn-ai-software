"""Sprint 56F.5 — Documentation Excellence Certification tests.

Verifies the certification engine scores ten quality dimensions, rolls them up
into the six headline scores, assigns a certification level, reaches the target
Overall Score >= 95 (Platinum), and reports the documentation as
customer-self-service ready.
"""

import pytest

from app.services.documentation_certification import (
    CERTIFICATION_TARGET,
    CERTIFICATION_THRESHOLDS,
    DocumentationCertificationEngine,
)
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
)

BASE = "/v1/customer-success"

EXPECTED_DIMENSIONS = {
    "technical_completeness", "content_depth", "screenshot_quality",
    "customer_readability", "training_value", "business_value",
    "troubleshooting_quality", "faq_quality", "playbook_coverage",
    "journey_coverage",
}
EXPECTED_SCORES = {
    "technical_score", "content_score", "screenshot_score",
    "training_score", "customer_success_score", "overall_score",
}


async def _org_token(client) -> str:
    _, tokens = await create_authenticated_user(
        client, email="cert@example.com", username="certuser"
    )
    org = await create_organization(client, tokens["access_token"], name="Cert Org")
    return org["context"]["access_token"]


# --------------------------------------------------------------------------- #
# Engine unit tests                                                           #
# --------------------------------------------------------------------------- #
def test_ten_dimensions_present_and_scored():
    report = DocumentationCertificationEngine().report()
    dims = report["dimensions"]
    assert len(dims) == 10
    assert {d["key"] for d in dims} == EXPECTED_DIMENSIONS
    for d in dims:
        assert 0 <= d["score"] <= 100, d["key"]
        assert d["signal"], d["key"]
        assert d["source"], d["key"]


def test_six_scores_present_and_in_range():
    scores = DocumentationCertificationEngine().report()["scores"]
    assert set(scores) == EXPECTED_SCORES
    for k, v in scores.items():
        assert 0 <= v <= 100, k


def test_overall_meets_target_and_platinum():
    cert = DocumentationCertificationEngine().report()["certification"]
    assert cert["overall_score"] >= CERTIFICATION_TARGET
    assert cert["meets_target"] is True
    assert cert["level"] == "Platinum"
    assert cert["target"] == CERTIFICATION_TARGET


def test_documentation_is_self_service_ready():
    cert = DocumentationCertificationEngine().report()["certification"]
    assert cert["self_service_ready"] is True


def test_certification_thresholds_exposed():
    cert = DocumentationCertificationEngine().report()["certification"]
    assert cert["thresholds"] == CERTIFICATION_THRESHOLDS
    assert CERTIFICATION_THRESHOLDS["Platinum"] == 95


def test_level_matches_overall_score():
    engine = DocumentationCertificationEngine()
    report = engine.report()
    overall = report["certification"]["overall_score"]
    expected = (
        "Platinum" if overall >= 95 else
        "Gold" if overall >= 85 else
        "Silver" if overall >= 75 else "Bronze"
    )
    assert report["certification"]["level"] == expected


def test_dashboard_structure():
    dash = DocumentationCertificationEngine().dashboard()
    assert "certification" in dash
    assert set(dash["scores"]) == EXPECTED_SCORES
    stats = dash["headline_stats"]
    assert stats["guides_certified"] > 0
    assert stats["training_videos"] > 0
    assert stats["playbooks"] == 5
    # With everything passing there should be no open opportunities.
    assert dash["opportunities"] == []
    assert dash["strengths"]


# --------------------------------------------------------------------------- #
# API tests                                                                   #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_certification_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/certification", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["dimensions"]) == 10
    assert set(body["scores"]) == EXPECTED_SCORES
    assert body["certification"]["level"] == "Platinum"
    assert body["certification"]["self_service_ready"] is True


@pytest.mark.asyncio
async def test_certification_dashboard_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(
        f"{BASE}/certification/dashboard", headers=auth_headers(token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["certification"]["overall_score"] >= CERTIFICATION_TARGET
    assert body["headline_stats"]["playbooks"] == 5
