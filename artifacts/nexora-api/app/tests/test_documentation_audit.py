"""Sprint 56F.1 — Documentation Content Audit Engine tests.

Verifies the audit engine:

* audits every customer-facing guide,
* measures the six content metrics,
* flags the eight weak-content conditions,
* assigns a quality score and the correct quality level,
* produces an audit dashboard and identifies weak guides automatically.
"""

import pytest

from app.services.customer_success_content import MODULES
from app.services.documentation_audit import (
    THIN_CONTENT_WORDS,
    DocumentationAuditEngine,
)
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
)

BASE = "/v1/customer-success"

METRIC_KEYS = {
    "word_count", "screenshot_count", "step_count",
    "faq_count", "troubleshooting_count", "example_count",
}
FLAG_KEYS = {
    "thin_content", "generic_content", "missing_screenshots",
    "missing_expected_results", "missing_business_value",
    "missing_examples", "missing_troubleshooting", "missing_faqs",
}
LEVELS = {"Poor", "Good", "Excellent", "Production Ready"}


async def _org_token(client) -> str:
    _, tokens = await create_authenticated_user(
        client, email="audit@example.com", username="audituser"
    )
    org = await create_organization(client, tokens["access_token"], name="Audit Org")
    return org["context"]["access_token"]


# --------------------------------------------------------------------------- #
# Engine unit tests                                                           #
# --------------------------------------------------------------------------- #
def test_every_guide_is_audited():
    engine = DocumentationAuditEngine()
    audits = engine.audit_all()
    assert len(audits) == len(MODULES)
    keys = {a["key"] for a in audits}
    assert keys == {m["key"] for m in MODULES}


def test_each_audit_has_metrics_flags_score_level():
    engine = DocumentationAuditEngine()
    for a in engine.audit_all():
        assert METRIC_KEYS == set(a["metrics"]), a["key"]
        assert FLAG_KEYS == set(a["flags"]), a["key"]
        assert 0 <= a["quality_score"] <= 100, a["key"]
        assert a["level"] in LEVELS, a["key"]
        # Score and level agree.
        score = a["quality_score"]
        expected = (
            "Production Ready" if score >= 95 else
            "Excellent" if score >= 80 else
            "Good" if score >= 60 else "Poor"
        )
        assert a["level"] == expected, (a["key"], score, a["level"])


def test_issues_and_recommendations_present_for_flagged_guides():
    engine = DocumentationAuditEngine()
    for a in engine.audit_all():
        flagged = any(a["flags"].values())
        if flagged:
            assert a["issues"], a["key"]
            assert a["recommendations"], a["key"]
        assert a["issue_count"] == len(a["issues"])


def test_thin_content_flag_matches_threshold():
    engine = DocumentationAuditEngine()
    for a in engine.audit_all():
        thin = a["metrics"]["word_count"] < THIN_CONTENT_WORDS
        assert a["flags"]["thin_content"] is thin, a["key"]


def test_report_dashboard_and_weak_identification():
    engine = DocumentationAuditEngine()
    report = engine.report()
    summary = report["summary"]
    assert summary["guides_audited"] == len(MODULES)
    assert 0 <= summary["average_score"] <= 100
    # Distribution sums to the number of guides.
    assert sum(report["level_distribution"].values()) == len(MODULES)
    # Issue totals cover every flag type.
    assert FLAG_KEYS == set(report["issue_totals"])
    # Weak guides are exactly those scoring below 80, and are surfaced.
    weak_keys = {w["key"] for w in report["weak_guides"]}
    computed = {a["key"] for a in engine.audit_all() if a["quality_score"] < 80}
    assert weak_keys == computed
    assert summary["weak_guides"] == len(weak_keys)
    # Guides are ordered weakest-first.
    scores = [g["quality_score"] for g in report["guides"]]
    assert scores == sorted(scores)


def test_audit_guide_lookup_and_404():
    engine = DocumentationAuditEngine()
    a = engine.audit_guide("monitoring")
    assert a["key"] == "monitoring"
    with pytest.raises(Exception):
        engine.audit_guide("does-not-exist")


# --------------------------------------------------------------------------- #
# API tests                                                                   #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_audit_report_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/documentation-audit", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["summary"]["guides_audited"] == len(MODULES)
    assert len(body["guides"]) == len(MODULES)
    for g in body["guides"]:
        assert "quality_score" in g
        assert g["level"] in LEVELS


@pytest.mark.asyncio
async def test_audit_guide_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(
        f"{BASE}/documentation-audit/guides/incidents", headers=auth_headers(token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["key"] == "incidents"
    assert set(body["metrics"]) == METRIC_KEYS


@pytest.mark.asyncio
async def test_audit_guide_unknown_returns_404(client):
    token = await _org_token(client)
    resp = await client.get(
        f"{BASE}/documentation-audit/guides/nope", headers=auth_headers(token)
    )
    assert resp.status_code == 404
