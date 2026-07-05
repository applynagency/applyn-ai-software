"""Sprint 56D.1 — Real Screenshot Asset Generation tests."""

import pytest

from app.services.screenshot_assets import AREAS, DEVICES, SHOTS, ScreenshotAssetGenerator
from app.services.ui_registry import route_exists
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
)

BASE = "/v1/customer-success"


async def _org_token(client) -> str:
    _, tokens = await create_authenticated_user(
        client, email="assets-docs@example.com", username="assetsdocs"
    )
    org = await create_organization(client, tokens["access_token"], name="Assets Docs Org")
    return org["context"]["access_token"]


def test_every_area_maps_to_a_real_route():
    assert len(AREAS) == 26
    for area in AREAS:
        assert route_exists(area["route"]), f"{area['page_name']} -> {area['route']}"


def test_manifest_covers_all_devices_and_shots():
    gen = ScreenshotAssetGenerator()
    manifest = gen.manifest()
    assert len(manifest) == len(AREAS) * len(DEVICES) * len(SHOTS) == 234
    required = {
        "screenshot_id", "page_name", "route", "title", "description",
        "device", "shot_type", "capture_date", "version",
    }
    for entry in manifest:
        assert required <= set(entry.keys())
        assert entry["device"] in DEVICES
        assert entry["shot_type"] in SHOTS
        assert entry["route_valid"] is True


def test_coverage_meets_target():
    cov = ScreenshotAssetGenerator().coverage()
    assert cov["coverage_percent"] >= 95
    assert cov["coverage_percent"] == 100
    assert cov["invalid"] == 0


def test_generate_writes_real_svg_files(tmp_path):
    gen = ScreenshotAssetGenerator(base_dir=tmp_path)
    result = gen.generate()
    assert result["generated"] == 234
    files = list(tmp_path.glob("*.svg"))
    assert len(files) == 234
    sample = (tmp_path / "monitoring-overview-desktop.svg").read_text()
    assert sample.startswith("<svg")
    assert "</svg>" in sample


def test_svg_renders_for_any_id_no_placeholder():
    gen = ScreenshotAssetGenerator()
    # Canonical id.
    svg = gen.svg_for_id("incidents-detail-mobile")
    assert "<svg" in svg and "</svg>" in svg
    # Arbitrary documentation step id still renders a real image (no placeholder).
    svg2 = gen.svg_for_id("incidents-step-1")
    assert "<svg" in svg2 and "</svg>" in svg2


@pytest.mark.asyncio
async def test_screenshot_assets_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/screenshot-assets", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["coverage"]["coverage_percent"] == 100
    assert len(body["items"]) == 234
    assert all(i["route_valid"] for i in body["items"])


@pytest.mark.asyncio
async def test_generate_endpoint(client):
    token = await _org_token(client)
    resp = await client.post(f"{BASE}/screenshot-assets/generate", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["generated"] == 234
    assert body["coverage_percent"] == 100


@pytest.mark.asyncio
async def test_screenshot_image_by_id_is_public(client):
    # No auth header — documentation <img> tags must load without a token.
    resp = await client.get(f"{BASE}/screenshots/dashboard-overview-desktop")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert resp.text.startswith("<svg")


@pytest.mark.asyncio
async def test_screenshot_render_by_route_is_public(client):
    resp = await client.get(f"{BASE}/screenshot-render?route=/monitoring&shot=overview&device=desktop")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in resp.text


@pytest.mark.asyncio
async def test_render_unknown_route_still_returns_image(client):
    resp = await client.get(f"{BASE}/screenshot-render?route=/unknown-xyz")
    assert resp.status_code == 200
    assert "<svg" in resp.text
