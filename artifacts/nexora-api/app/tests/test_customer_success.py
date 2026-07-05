"""Sprint 56A — Customer Success Documentation Platform tests."""

import pytest

from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
)

BASE = "/v1/customer-success"


async def _org_token(client) -> str:
    _, tokens = await create_authenticated_user(
        client, email="cs@example.com", username="csuser"
    )
    org = await create_organization(client, tokens["access_token"], name="CS Org")
    return org["context"]["access_token"]


@pytest.mark.asyncio
async def test_requires_authentication(client):
    resp = await client.get(f"{BASE}/portal")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_portal_aggregates_everything(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/portal", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["counts"]["journeys"] == 4
    assert body["counts"]["playbooks"] == 8
    assert body["counts"]["success_center"] == 7
    assert body["counts"]["modules"] >= 10
    # Quality target met for all customer-facing modules.
    assert body["quality"]["passes_target"] is True
    assert body["quality"]["average_score"] >= 95
    assert body["screenshots"]["total"] > 0


@pytest.mark.asyncio
async def test_modules_list_and_detail_are_maturity_complete(client):
    token = await _org_token(client)
    listed = await client.get(f"{BASE}/modules", headers=auth_headers(token))
    assert listed.status_code == 200, listed.text
    items = listed.json()["items"]
    assert items, "expected at least one module"

    for summary in items:
        detail = await client.get(
            f"{BASE}/modules/{summary['key']}", headers=auth_headers(token)
        )
        assert detail.status_code == 200, detail.text
        m = detail.json()
        # Overview — all five sub-sections.
        for field in ("what", "why", "business_value", "who", "when"):
            assert m["overview"][field].strip()
        # Navigation path metadata.
        assert m["navigation"]["path"]
        assert m["navigation"]["route"]
        # Prerequisites.
        assert len(m["prerequisites"]) >= 1
        # Steps — minimum 5, each with action/expected/screenshot.
        assert len(m["steps"]) >= 5
        for step in m["steps"]:
            assert step["action"] and step["expected"] and step["screenshot"]
        # Results interpretation.
        assert len(m["interpretation"]) >= 1
        # Real-world example.
        for field in ("scenario", "walkthrough", "outcome"):
            assert m["example"][field].strip()
        # Troubleshooting + best practices.
        assert len(m["troubleshooting"]) >= 1
        assert len(m["best_practices"]) >= 1
        # FAQ — minimum 5.
        assert len(m["faq"]) >= 5
        # Screenshot placeholders.
        assert len(m["screenshots"]) >= 3
        # Portal metadata.
        assert m["metadata"]["reading_time_minutes"] > 0
        assert m["metadata"]["difficulty"]
        assert m["metadata"]["role"]


@pytest.mark.asyncio
async def test_unknown_module_returns_404(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/modules/not-a-real-module", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_journeys_generated(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/journeys", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    keys = {j["key"] for j in items}
    assert {
        "infrastructure-onboarding",
        "incident-management",
        "safe-deployment",
        "executive-reporting",
    } <= keys
    for j in items:
        assert j["stages"]
        assert j["expected_outcomes"]
        for stage in j["stages"]:
            assert stage["title"] and stage["expected_outcome"] and stage["screenshot"]


@pytest.mark.asyncio
async def test_integration_playbooks_generated(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/playbooks", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    keys = {p["key"] for p in items}
    assert {
        "aws", "azure", "kubernetes", "github", "gitlab", "slack",
        "microsoft-teams", "jira",
    } <= keys
    for p in items:
        assert p["overview"] and p["architecture_diagram"]
        assert p["required_permissions"] and p["credential_setup"]
        assert p["validation_steps"] and p["expected_results"]
        assert p["common_errors"] and p["security_notes"] and p["best_practices"]


@pytest.mark.asyncio
async def test_success_center_generated(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/success-center", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    keys = {g["key"] for g in items}
    assert {
        "first-15-minutes",
        "first-incident",
        "first-deployment",
        "first-postmortem",
        "first-executive-report",
        "first-slo",
        "first-cost-review",
    } <= keys
    for g in items:
        assert g["difficulty"] == "Beginner"
        assert len(g["steps"]) >= 5


@pytest.mark.asyncio
async def test_screenshot_manifest(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/screenshots", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] > 0
    for entry in body["items"]:
        assert entry["page_name"]
        assert entry["route"]
        assert entry["screenshot_name"]
        assert entry["screenshot_category"] in body["summary"]["categories"]
        assert entry["description"]
        assert entry["capture_priority"] in ("high", "medium", "low")

    # Category filtering.
    filtered = await client.get(
        f"{BASE}/screenshots?category=incident", headers=auth_headers(token)
    )
    assert filtered.status_code == 200
    for entry in filtered.json()["items"]:
        assert entry["screenshot_category"] == "incident"


@pytest.mark.asyncio
async def test_quality_engine_meets_target(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/quality", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    report = resp.json()
    assert report["target"] == 95
    assert report["passes_target"] is True
    assert report["production_ready_count"] == report["modules_total"]
    # Sprint 56A.1 expanded the rubric to 10 weighted components.
    assert len(report["dimensions"]) == 10
    for module in report["modules"]:
        assert module["coverage_score"] >= 95
        assert module["level"] == "Production Ready"
        assert module["missing_dimensions"] == []
