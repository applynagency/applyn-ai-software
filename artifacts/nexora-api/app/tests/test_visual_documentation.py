"""Sprint 56B — Visual Documentation & Screenshot Automation tests."""

import pytest

from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
)

BASE = "/v1/customer-success"


async def _org_token(client) -> str:
    _, tokens = await create_authenticated_user(
        client, email="visual-docs@example.com", username="visualdocs"
    )
    org = await create_organization(client, tokens["access_token"], name="Visual Docs Org")
    return org["context"]["access_token"]


@pytest.mark.asyncio
async def test_capture_engine(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/captures", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] > 0
    e = body["items"][0]
    for field in (
        "page_name", "route", "module", "category", "device",
        "capture_type", "screenshot_path", "captured", "captured_at", "version",
    ):
        assert field in e
    # Device filter works.
    mobile = await client.get(f"{BASE}/captures?device=mobile", headers=auth_headers(token))
    assert mobile.status_code == 200
    assert all(i["device"] == "mobile" for i in mobile.json()["items"])


@pytest.mark.asyncio
async def test_embedded_screenshot_metadata(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/modules/incidents", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    steps = resp.json()["steps"]
    assert steps
    for s in steps:
        assert s["screenshot_id"]
        assert s["caption"]
        assert s["alt_text"]
        assert s["expected"]


@pytest.mark.asyncio
async def test_annotations(client):
    token = await _org_token(client)
    summary = await client.get(f"{BASE}/annotations/summary", headers=auth_headers(token))
    assert summary.status_code == 200, summary.text
    sbody = summary.json()
    assert sbody["annotated_screenshots"] > 0
    assert sbody["total_annotations"] > 0
    assert set(sbody["by_kind"].keys()) == {"highlight", "callout", "label", "arrow"}
    # Annotation detail for a known screenshot.
    detail = await client.get(
        f"{BASE}/annotations?screenshot_id=incidents-overview", headers=auth_headers(token)
    )
    assert detail.status_code == 200
    dbody = detail.json()
    assert dbody["total"] > 0
    a = dbody["annotations"][0]
    for field in ("screenshot_id", "kind", "target", "description", "region"):
        assert field in a


@pytest.mark.asyncio
async def test_navigation_maps(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/navigation-maps", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] >= 4
    nm = body["items"][0]
    assert nm["flow"]
    assert nm["nodes"]
    node = nm["nodes"][0]
    for field in ("page_name", "route", "page_screenshot", "navigation_screenshot", "expected_screens"):
        assert field in node


@pytest.mark.asyncio
async def test_journey_walkthroughs(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/journey-walkthroughs", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 4
    for j in body["items"]:
        assert j["steps"]
        for step in j["steps"]:
            assert step["screenshot"]
            assert step["expected_result"]
            assert step["navigation_path"]


@pytest.mark.asyncio
async def test_integration_visuals(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/integration-visuals", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    keys = {i["key"] for i in body["items"]}
    assert {
        "aws", "azure", "kubernetes", "github",
        "gitlab", "slack", "microsoft-teams", "jira",
    } <= keys
    detail = await client.get(f"{BASE}/integration-visuals/aws", headers=auth_headers(token))
    assert detail.status_code == 200
    d = detail.json()
    assert d["architecture_diagram"].startswith("graph")
    set_keys = {s["key"] for s in d["screen_sets"]}
    assert {"credential_setup", "validation", "success", "troubleshooting", "expected_output"} <= set_keys
    missing = await client.get(f"{BASE}/integration-visuals/nope", headers=auth_headers(token))
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_screenshot_gallery_with_filters(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/gallery", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] > 0
    facets = body["facets"]
    for f in ("modules", "workflows", "journeys", "integrations", "roles", "devices"):
        assert f in facets
    item = body["items"][0]
    for field in ("screenshot_id", "screenshot_path", "title", "description", "related_guide"):
        assert field in item
    # Integration filter narrows results.
    aws = await client.get(f"{BASE}/gallery?integration=aws", headers=auth_headers(token))
    assert aws.status_code == 200
    aws_items = aws.json()["items"]
    assert aws_items and all(i["integration"] == "aws" for i in aws_items)


@pytest.mark.asyncio
async def test_visual_coverage_dashboard(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/visual-coverage", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["platform"]["coverage_percent"] >= 95
    for scope in ("by_module", "by_device", "by_journey", "by_integration", "by_capture_type"):
        assert body[scope]
    assert body["release_ready"] is True


@pytest.mark.asyncio
async def test_visual_readiness_endpoint(client):
    token = await _org_token(client)
    resp = await client.get("/v1/docs/visual-readiness", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for field in (
        "screenshot_coverage", "annotated_screenshots", "journeys_visualized",
        "integrations_visualized", "documentation_visual_score", "release_ready",
    ):
        assert field in body
    assert body["screenshot_coverage"] >= 95
    assert body["journeys_visualized"] == 4
    assert body["integrations_visualized"] == 8
    assert body["documentation_visual_score"] >= 95
    assert body["release_ready"] is True


@pytest.mark.asyncio
async def test_visual_readiness_requires_auth(client):
    resp = await client.get("/v1/docs/visual-readiness")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
@pytest.mark.parametrize("fmt,media", [
    ("pdf", "application/pdf"),
    ("html", "text/html"),
    ("markdown", "text/markdown"),
])
async def test_documentation_export_formats(client, fmt, media):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/export?format={fmt}", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith(media)
    assert len(resp.content) > 0
    if fmt == "pdf":
        assert resp.content[:5] == b"%PDF-"
    else:
        text = resp.content.decode()
        # Export includes screenshots, architecture diagrams, and navigation maps.
        assert "Architecture Diagrams" in text
        assert "Navigation Maps" in text
        assert "Screenshot" in text or "screenshot" in text
