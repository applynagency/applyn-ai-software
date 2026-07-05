"""Sprint 56C — Documentation Reality Verification & Drift Detection tests."""

import pytest

from app.services.documentation_verification import classify
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
)

BASE = "/v1/customer-success"


async def _org_token(client) -> str:
    _, tokens = await create_authenticated_user(
        client, email="verify-docs@example.com", username="verifydocs"
    )
    org = await create_organization(client, tokens["access_token"], name="Verify Docs Org")
    return org["context"]["access_token"]


@pytest.mark.asyncio
async def test_screenshot_verification_engine(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/verifications", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] > 0
    rec = body["items"][0]
    for field in (
        "screenshot_id", "route", "page_name", "module", "ui_version",
        "screenshot_version", "verification_status",
    ):
        assert field in rec
    assert rec["verification_status"] in ("PENDING", "VERIFIED", "OUTDATED", "BROKEN")
    # Status filter works.
    outdated = await client.get(f"{BASE}/verifications?status=OUTDATED", headers=auth_headers(token))
    assert outdated.status_code == 200
    assert all(r["verification_status"] == "OUTDATED" for r in outdated.json()["items"])


def test_classify_rules():
    assert classify(route="/nope", module="ghost", captured=True, screenshot_id="x") == "BROKEN"
    assert classify(route="/monitoring", module="ghost", captured=True, screenshot_id="x") == "BROKEN"
    assert classify(route="/monitoring", module="monitoring", captured=False, screenshot_id="x") == "PENDING"
    assert classify(route="/monitoring", module="monitoring", captured=True, screenshot_id="x") == "VERIFIED"
    assert classify(
        route="/documentation", module="executive-reports", captured=True,
        screenshot_id="documentation-full_page-desktop",
    ) == "OUTDATED"


@pytest.mark.asyncio
async def test_verification_summary(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/verification-summary", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["broken_screenshots"] == 0
    assert body["verified_percent"] >= 95
    assert set(body["by_status"].keys()) == {"PENDING", "VERIFIED", "OUTDATED", "BROKEN"}


@pytest.mark.asyncio
async def test_screenshot_lifecycle(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/lifecycle", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    item = resp.json()["items"][0]
    for field in ("created_at", "updated_at", "verified_at", "last_used_at", "verification_count"):
        assert field in item
    report = await client.get(f"{BASE}/lifecycle-report", headers=auth_headers(token))
    assert report.status_code == 200
    rbody = report.json()
    for scope in ("by_module", "by_integration", "by_journey", "by_guide"):
        assert rbody[scope]


@pytest.mark.asyncio
async def test_drift_detection(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/drift", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "items" in body and "by_severity" in body
    assert set(body["by_severity"].keys()) == {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    for item in body["items"]:
        for field in ("affected_module", "screenshot_count", "impacted_guides", "severity", "recommended_action"):
            assert field in item
        assert item["severity"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")


@pytest.mark.asyncio
async def test_navigation_validation(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/navigation-health", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_paths"] > 0
    assert body["valid_paths"] + body["broken_paths"] == body["total_paths"]
    assert body["health_score"] >= 95


@pytest.mark.asyncio
async def test_journey_verification(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/journey-verification", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 4
    for j in body["journeys"]:
        assert j["status"] in ("PASS", "WARNING", "FAIL")
    assert body["journey_health"] >= 95


@pytest.mark.asyncio
async def test_consistency_engine(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/consistency", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert 0 <= body["consistency_score"] <= 100
    assert body["consistency_score"] >= 95
    assert body["checks"]


@pytest.mark.asyncio
async def test_verification_dashboard(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/verification-dashboard", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for w in (
        "verified_screenshots", "outdated_screenshots", "broken_screenshots",
        "navigation_health", "journey_health", "consistency_score", "drift_alerts",
    ):
        assert w in body
    for f in ("modules", "integrations", "journeys", "guide_types"):
        assert f in body["facets"]


@pytest.mark.asyncio
async def test_release_gates(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/release-report", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    gate_names = {g["gate"] for g in body["gates"]}
    assert {"screenshot_coverage", "verified_screenshots", "navigation_health", "consistency_score"} <= gate_names
    assert body["release_ready"] is True


@pytest.mark.asyncio
async def test_verification_run_writes_audit_trail(client):
    token = await _org_token(client)
    run = await client.post(f"{BASE}/verify", headers=auth_headers(token))
    assert run.status_code == 200, run.text
    assert run.json()["events_recorded"] > 0
    trail = await client.get(f"{BASE}/verification-audit", headers=auth_headers(token))
    assert trail.status_code == 200
    actions = {e["action"] for e in trail.json()["items"]}
    assert "release_gate_evaluated" in actions
    assert "navigation_verified" in actions
    assert "journey_verified" in actions


@pytest.mark.asyncio
async def test_audit_trail_is_org_scoped(client):
    # Org A runs verification.
    token_a = await _org_token(client)
    await client.post(f"{BASE}/verify", headers=auth_headers(token_a))
    # A fresh org B sees no audit events from A.
    _, tokens_b = await create_authenticated_user(
        client, email="verify-b@example.com", username="verifyb"
    )
    org_b = await create_organization(client, tokens_b["access_token"], name="Verify Org B")
    token_b = org_b["context"]["access_token"]
    trail_b = await client.get(f"{BASE}/verification-audit", headers=auth_headers(token_b))
    assert trail_b.status_code == 200
    assert trail_b.json()["total"] == 0


@pytest.mark.asyncio
async def test_verification_readiness_endpoint(client):
    token = await _org_token(client)
    resp = await client.get("/v1/docs/verification-readiness", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for field in (
        "verified_screenshots", "outdated_screenshots", "broken_screenshots",
        "navigation_health", "journey_health", "consistency_score",
        "documentation_verification_score", "release_ready",
    ):
        assert field in body
    assert body["documentation_verification_score"] >= 95
    assert body["broken_screenshots"] == 0
    assert body["release_ready"] is True


@pytest.mark.asyncio
async def test_verification_readiness_requires_auth(client):
    resp = await client.get("/v1/docs/verification-readiness")
    assert resp.status_code in (401, 403)
