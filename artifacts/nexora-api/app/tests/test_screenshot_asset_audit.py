"""Sprint 56F.7 — Screenshot Asset Path Audit tests.

Verifies the audit engine:

* finds every generated screenshot reference across modules/journeys/playbooks/
  success-center (and step/stage shots),
* records screenshot_id, image_path, article_id and module for each,
* verifies filesystem existence, static serving path and frontend URL resolution,
* produces the required report counts and identifies the root cause of any failure,
* exposes GET /v1/docs/screenshot-audit,
* and proves every reference resolves to HTTP 200 (no 404 URLs).
"""

import pytest

from app.services.screenshot_asset_audit import (
    SERVE_PREFIX,
    ScreenshotAssetAuditEngine,
)
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
)

BASE = "/v1/docs"

REPORT_KEYS = {
    "total_references", "valid_files", "missing_files",
    "broken_urls", "invalid_static_routes",
}
ITEM_KEYS = {
    "screenshot_id", "filename", "image_path", "article_id", "module",
    "url", "file_exists", "static_route_valid", "url_resolves",
    "served_dynamically", "status", "root_cause",
}


async def _org_token(client) -> str:
    _, tokens = await create_authenticated_user(
        client, email="shotaudit@example.com", username="shotaudituser"
    )
    org = await create_organization(client, tokens["access_token"], name="Shot Audit Org")
    return org["context"]["access_token"]


# --------------------------------------------------------------------------- #
# Engine unit tests                                                           #
# --------------------------------------------------------------------------- #
def test_finds_references_and_required_fields():
    report = ScreenshotAssetAuditEngine().report()
    shots = report["screenshots"]
    assert len(shots) > 50  # every guide contributes many references
    for s in shots:
        assert ITEM_KEYS == set(s), s.get("screenshot_id")
        assert s["screenshot_id"]
        assert s["article_id"]
        assert s["module"]
        assert s["image_path"].endswith(f"{s['screenshot_id']}.svg")


def test_report_has_required_counts():
    report = ScreenshotAssetAuditEngine().report()["report"]
    assert REPORT_KEYS == set(report)
    total = report["total_references"]
    assert total == (
        report["valid_files"]
        + report["missing_files"]
        + report["broken_urls"]
        + report["invalid_static_routes"]
    )


def test_every_reference_resolves_http_200():
    """Acceptance: every screenshot reference resolves — no 404 URLs."""
    report = ScreenshotAssetAuditEngine().report()
    counts = report["report"]
    assert counts["total_references"] > 0
    assert counts["valid_files"] == counts["total_references"]
    assert counts["missing_files"] == 0
    assert counts["broken_urls"] == 0
    assert counts["invalid_static_routes"] == 0
    assert report["failures"] == []
    assert report["summary"]["all_resolve"] is True


def test_every_url_uses_canonical_serving_prefix():
    shots = ScreenshotAssetAuditEngine().report()["screenshots"]
    for s in shots:
        assert s["url"] == f"{SERVE_PREFIX}/{s['screenshot_id']}"
        assert s["static_route_valid"] is True
        assert s["url_resolves"] is True


def test_failures_carry_root_cause():
    report = ScreenshotAssetAuditEngine().report()
    for f in report["failures"]:
        assert f["status"] != "ok"
        assert f["root_cause"]


def test_summary_breakdown_is_consistent():
    report = ScreenshotAssetAuditEngine().report()
    summary = report["summary"]
    shots = report["screenshots"]
    assert summary["total_references"] == len(shots)
    assert summary["resolving"] == sum(1 for s in shots if s["url_resolves"])
    assert summary["served_dynamically"] == sum(1 for s in shots if s["served_dynamically"])
    assert summary["serving_prefix"] == SERVE_PREFIX


# --------------------------------------------------------------------------- #
# API tests                                                                   #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_screenshot_audit_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/screenshot-audit", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert REPORT_KEYS == set(body["report"])
    assert body["report"]["valid_files"] == body["report"]["total_references"]
    assert body["report"]["broken_urls"] == 0
    assert body["failures"] == []
    assert body["summary"]["all_resolve"] is True


@pytest.mark.asyncio
async def test_screenshot_audit_requires_auth(client):
    resp = await client.get(f"{BASE}/screenshot-audit")
    assert resp.status_code in (401, 403)
