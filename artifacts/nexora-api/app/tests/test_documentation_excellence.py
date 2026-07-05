"""Sprint 56A.1 — Documentation Excellence & Customer Adoption Layer tests."""

import pytest

from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
)

BASE = "/v1/customer-success"


async def _org_token(client) -> str:
    _, tokens = await create_authenticated_user(
        client, email="docs-excellence@example.com", username="docsexcellence"
    )
    org = await create_organization(client, tokens["access_token"], name="Docs Excellence Org")
    return org["context"]["access_token"]


@pytest.mark.asyncio
async def test_screenshot_coverage_system(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/screenshot-coverage", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Per-page metadata.
    assert body["pages"], "expected tracked pages"
    page = body["pages"][0]
    for field in (
        "page_name", "route", "module", "screenshot_required",
        "screenshot_available", "screenshot_priority", "release_blocking",
    ):
        assert field in page
    # Metrics per scope + platform.
    metrics = body["metrics"]
    assert metrics["by_module"] and metrics["by_journey"] and metrics["by_integration"]
    platform = body["platform"]
    assert 0 <= platform["coverage_percent"] <= 100
    assert platform["level"] in ("Poor", "Needs Work", "Good", "Release Ready")
    # No high-priority screenshot is left release-blocking.
    assert body["release_blocking"] == []


@pytest.mark.asyncio
async def test_documentation_dashboard(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/dashboard", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["modules"]) >= 8
    row = body["modules"][0]
    for field in (
        "module", "name", "coverage_score", "screenshot_coverage",
        "guide_count", "last_updated",
    ):
        assert field in row
    assert body["passes_target"] is True
    assert all(r["coverage_score"] >= 95 for r in body["modules"])


@pytest.mark.asyncio
async def test_quality_uses_ten_weighted_components(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/quality", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    module = body["modules"][0]
    dims = module["dimensions"]
    for required in ("architecture_diagram", "expected_results", "overview", "screenshots"):
        assert required in dims
    assert len(dims) == 10
    assert body["average_score"] >= 95


@pytest.mark.asyncio
async def test_what_happens_internally_and_expected_screens(client):
    token = await _org_token(client)
    for key in ("monitoring", "incidents", "deployment-safety", "change-failure", "cost"):
        resp = await client.get(f"{BASE}/modules/{key}", headers=auth_headers(token))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # What Happens Internally.
        internal = body["internal"]
        assert internal["customer_action"]
        assert internal["engines"]
        assert internal["outputs"]
        # Architecture diagram + module-level expected screens.
        assert body["architecture_diagram"].startswith("graph")
        assert body["expected_screens"]
        # Every step has an expected result and an expected screen.
        assert body["steps"]
        for step in body["steps"]:
            assert step["expected"]
            assert step["expected_screens"]


@pytest.mark.asyncio
async def test_architecture_diagram_library(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/architecture", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    keys = {d["key"] for d in body["items"]}
    assert {
        "aws", "azure", "kubernetes", "github",
        "gitlab", "slack", "microsoft-teams", "jira",
    } <= keys
    detail = await client.get(f"{BASE}/architecture/aws", headers=auth_headers(token))
    assert detail.status_code == 200
    diagram = detail.json()
    assert diagram["mermaid"].startswith("graph")
    for field in ("source_systems", "data_flow", "processing_layer", "platform_components", "outputs"):
        assert diagram[field]


@pytest.mark.asyncio
async def test_unknown_architecture_returns_404(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/architecture/nope", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_learning_paths_with_progress(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/learning-paths", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    keys = {p["key"] for p in body["items"]}
    assert {
        "platform-fundamentals", "sre-operations",
        "safe-deployments", "reliability-leadership",
    } <= keys
    # Progress tracking responds to completed query.
    resp2 = await client.get(
        f"{BASE}/learning-paths/platform-fundamentals?completed=onboarding,monitoring",
        headers=auth_headers(token),
    )
    assert resp2.status_code == 200
    path = resp2.json()
    assert path["total_guides"] == 4
    assert path["completed_guides"] == 3
    assert path["remaining_guides"] == 1
    assert path["completion_percent"] == 75


@pytest.mark.asyncio
async def test_integration_validation_playbooks(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/playbooks/aws", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["validation_checklist"]
    assert body["expected_outputs"]
    assert body["common_errors"]
    assert body["recovery_steps"]


@pytest.mark.asyncio
async def test_documentation_readiness_endpoint(client):
    token = await _org_token(client)
    resp = await client.get("/v1/docs/readiness", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for field in (
        "documentation_score", "screenshot_coverage", "modules_ready",
        "modules_total", "journeys_ready", "integrations_ready", "release_ready",
    ):
        assert field in body
    assert body["documentation_score"] >= 95
    assert body["modules_ready"] == body["modules_total"]
    assert body["integrations_ready"] == 8
    assert body["journeys_ready"] == 4
    assert body["release_ready"] is True


@pytest.mark.asyncio
async def test_readiness_requires_auth(client):
    resp = await client.get("/v1/docs/readiness")
    assert resp.status_code in (401, 403)
