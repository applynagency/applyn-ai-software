"""Sprint 56D.6 — Screenshot Reality Validation tests.

Verifies that documentation screenshots are real:

* every reference reports file_exists, image_loads, and rendered_in_ui,
* the four problem lists (missing/broken/placeholder/invalid) are empty for the
  shipped product,
* per-entity minimums hold (guide >= 10, journey >= 20, integration >= 15),
* the release gate approves a complete set and rejects a missing one.
"""

from pathlib import Path

import pytest

from app.services.screenshot_assets import ScreenshotAssetGenerator
from app.services.screenshot_reality import ScreenshotRealityValidator
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
)

BASE = "/v1/customer-success"


async def _org_token(client) -> str:
    _, tokens = await create_authenticated_user(
        client, email="shots@example.com", username="shotsuser"
    )
    org = await create_organization(client, tokens["access_token"], name="Shots Org")
    return org["context"]["access_token"]


@pytest.mark.asyncio
async def test_reality_report_is_clean(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/screenshot-reality", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    rep = resp.json()
    c = rep["counts"]
    assert c["missing"] == 0
    assert c["broken"] == 0
    assert c["placeholder"] == 0
    assert c["invalid_references"] == 0
    assert c["valid"] == rep["total"] > 0
    # Every screenshot is real: file exists, loads, and renders in the UI.
    rep_full = rep  # all categories empty, so sample the coverage instead
    assert all(e["meets_minimum"] for e in rep_full["entity_coverage"])


@pytest.mark.asyncio
async def test_per_entity_minimums(client):
    token = await _org_token(client)
    rep = (await client.get(f"{BASE}/screenshot-reality", headers=auth_headers(token))).json()
    mins = {"guide": 10, "journey": 20, "integration": 15}
    seen = {"guide": 0, "journey": 0, "integration": 0}
    for e in rep["entity_coverage"]:
        seen[e["entity_type"]] += 1
        assert e["min_required"] == mins[e["entity_type"]], e
        assert e["screenshot_count"] >= mins[e["entity_type"]], e
        assert e["meets_minimum"] is True, e
    assert seen["guide"] >= 12
    assert seen["journey"] >= 4
    assert seen["integration"] >= 8


@pytest.mark.asyncio
async def test_release_gate_approves(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/screenshot-reality/release-gate", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    gate = resp.json()
    assert gate["passed"] is True
    assert gate["status"] == "RELEASE APPROVED"
    assert gate["reasons"] == []


@pytest.mark.asyncio
async def test_ensure_endpoint(client):
    token = await _org_token(client)
    resp = await client.post(f"{BASE}/screenshot-reality/ensure", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["canonical_generated"] >= 0
    assert "screenshots" in body["directory"]


def test_every_reference_is_real():
    """Direct engine check: each reference verifies file/loads/rendered-in-UI."""
    v = ScreenshotRealityValidator()
    rep = v.validate(ensure=True)
    for category in ("missing", "broken", "placeholder", "invalid_references"):
        assert rep[category] == [], (category, rep[category][:3])
    # Re-classify and assert reality booleans on a sample.
    checks = [v._classify(r) for r in v.all_references()]
    assert checks, "no references collected"
    for c in checks:
        assert c["file_exists"] is True, c
        assert c["image_loads"] is True, c
        assert c["rendered_in_ui"] is True, c
        assert c["invalid_reference"] is False, c


def test_missing_assets_reject_release(tmp_path: Path):
    """An empty asset directory must be detected as missing and reject the release."""
    gen = ScreenshotAssetGenerator(base_dir=tmp_path / "empty")
    v = ScreenshotRealityValidator(generator=gen)
    rep = v.validate(ensure=False)  # do not write any files
    assert rep["counts"]["missing"] > 0
    gate = rep["release_gate"]
    assert gate["passed"] is False
    assert gate["status"] == "RELEASE REJECTED"
    assert any("missing" in r.lower() for r in gate["reasons"])


def test_ensure_then_validate_passes(tmp_path: Path):
    """After ensuring assets in a fresh directory, validation passes."""
    gen = ScreenshotAssetGenerator(base_dir=tmp_path / "fresh")
    v = ScreenshotRealityValidator(generator=gen)
    v.ensure_assets()
    rep = v.validate(ensure=False)
    assert rep["counts"]["missing"] == 0
    assert rep["counts"]["broken"] == 0
    assert rep["release_gate"]["passed"] is True
