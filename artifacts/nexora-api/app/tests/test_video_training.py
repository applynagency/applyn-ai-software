"""Sprint 56E.2 — Video Training Platform tests.

Verifies the VideoTrainingEngine produces visual learning assets:

* every major module has 3 training videos (2-min overview, 5-min walkthrough,
  10-min deep dive),
* every scene carries narration, screen, expected action, and voice-over text,
* every video carries video / GIF / thumbnail metadata,
* categories (Beginner / Intermediate / Advanced) are assigned,
* portal sections (Video Library, Featured Videos, Recently Added) work,
* scripts export to markdown / html / pdf.
"""

import pytest

from app.services.customer_success_content import MODULES
from app.services.video_training import VIDEO_KINDS, VideoTrainingEngine
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
)

BASE = "/v1/customer-success"

REQUIRED_SCENE_FIELDS = [
    "order", "title", "duration_seconds", "timecode",
    "narration", "voice_over", "on_screen_text", "expected_action", "screen",
]
REQUIRED_SCREEN_FIELDS = ["route", "shot", "device", "screenshot_id", "thumbnail_url"]
KIND_CATEGORY = {"overview": "Beginner", "walkthrough": "Intermediate", "deep-dive": "Advanced"}
KIND_DURATION = {"overview": 120, "walkthrough": 300, "deep-dive": 600}


async def _org_token(client) -> str:
    _, tokens = await create_authenticated_user(
        client, email="video@example.com", username="videouser"
    )
    org = await create_organization(client, tokens["access_token"], name="Video Org")
    return org["context"]["access_token"]


# --------------------------------------------------------------------------- #
# Engine-level unit tests                                                      #
# --------------------------------------------------------------------------- #
def test_every_module_has_three_videos():
    engine = VideoTrainingEngine()
    lib = engine.library()
    assert lib["library_total"] == len(MODULES) * 3
    for m in MODULES:
        items = engine.for_module(m["key"])["items"]
        kinds = {v["kind"] for v in items}
        assert kinds == {s["kind"] for s in VIDEO_KINDS}, m["key"]


def test_video_durations_and_categories():
    engine = VideoTrainingEngine()
    for v in engine.library()["items"]:
        assert v["category"] == KIND_CATEGORY[v["kind"]]
        assert v["duration_seconds"] == KIND_DURATION[v["kind"]]


def test_every_scene_is_complete():
    engine = VideoTrainingEngine()
    for summary in engine.library()["items"]:
        v = engine.get(summary["id"])
        assert v["scenes"], v["id"]
        total = 0
        for scene in v["scenes"]:
            for field in REQUIRED_SCENE_FIELDS:
                assert str(scene.get(field, "")).strip() != "" or field == "order", (v["id"], field)
            for field in REQUIRED_SCREEN_FIELDS:
                assert str(scene["screen"].get(field, "")).strip(), (v["id"], field)
            assert scene["screen"]["route"].startswith("/"), v["id"]
            total += scene["duration_seconds"]
        # Scene durations sum exactly to the video runtime.
        assert total == v["duration_seconds"], v["id"]


def test_every_video_has_all_metadata():
    engine = VideoTrainingEngine()
    for summary in engine.library()["items"]:
        v = engine.get(summary["id"])
        for key in ("video_metadata", "gif_metadata", "thumbnail_metadata"):
            assert v[key], (v["id"], key)
        assert v["video_metadata"]["format"] == "mp4"
        assert v["gif_metadata"]["format"] == "gif"
        assert v["thumbnail_metadata"]["url"].startswith("/nexora-api/")
        assert v["video_metadata"]["has_captions"] is True


def test_deep_dive_has_substantial_walkthrough():
    engine = VideoTrainingEngine()
    v = engine.get("monitoring-deep-dive")
    # Deep dive includes all walkthrough steps plus framing scenes.
    assert v["scene_count"] >= 15


# --------------------------------------------------------------------------- #
# Portal / API tests                                                          #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_video_library_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/videos", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["library_total"] == len(MODULES) * 3
    facets = body["facets"]
    assert facets["categories"] == {
        "Beginner": len(MODULES), "Intermediate": len(MODULES), "Advanced": len(MODULES),
    }
    assert facets["modules"] == len(MODULES)


@pytest.mark.asyncio
async def test_video_library_category_filter(client):
    token = await _org_token(client)
    resp = await client.get(
        f"{BASE}/videos?category=Advanced", headers=auth_headers(token)
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert items and all(v["category"] == "Advanced" for v in items)
    assert all(v["kind"] == "deep-dive" for v in items)


@pytest.mark.asyncio
async def test_featured_videos_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/videos/featured", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert items
    assert all(v["featured"] for v in items)


@pytest.mark.asyncio
async def test_recently_added_endpoint_sorted_desc(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/videos/recently-added", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert items
    dates = [v["added_at"] for v in items]
    assert dates == sorted(dates, reverse=True)


@pytest.mark.asyncio
async def test_videos_by_module_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(
        f"{BASE}/videos/by-module/incidents", headers=auth_headers(token)
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert len(items) == 3
    assert all(v["module"] == "incidents" for v in items)


@pytest.mark.asyncio
async def test_get_single_video_with_scenes(client):
    token = await _org_token(client)
    resp = await client.get(
        f"{BASE}/videos/deployment-safety-walkthrough", headers=auth_headers(token)
    )
    assert resp.status_code == 200, resp.text
    v = resp.json()
    assert v["category"] == "Intermediate"
    assert v["scenes"]
    first = v["scenes"][0]
    assert first["voice_over"]
    assert first["screen"]["thumbnail_url"]


@pytest.mark.asyncio
async def test_unknown_video_returns_404(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/videos/nope-overview", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_video_script_export(client):
    token = await _org_token(client)
    for fmt, ctype in (("markdown", "text/markdown"), ("html", "text/html"), ("pdf", "application/pdf")):
        resp = await client.get(
            f"{BASE}/videos/monitoring-overview/export?format={fmt}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200, resp.text
        assert ctype in resp.headers["content-type"]
        assert resp.content
