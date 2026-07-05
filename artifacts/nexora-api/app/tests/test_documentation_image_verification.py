"""Sprint 56F.8 — Documentation Image Rendering Verification tests.

Verifies that the engine:

* extracts every rendered image source from articles (gallery + inline),
* compares the stored URL against the canonical screenshot URL,
* classifies the root cause (stale reference / old PNG / missing BASE_PATH),
* produces the required report counts and per-broken-image detail,
* repairs stored URLs so every image renders,
* and exposes GET /v1/docs/image-rendering + POST .../repair.
"""

from app.core.config import settings
from app.services.documentation_image_verification import (
    CANON_PREFIX,
    canonical_url,
    classify,
    is_canonical,
    screenshot_id_from_url,
)
from app.tests.conftest import auth_headers, create_authenticated_user

H = auth_headers
STALE = "/static/docs/screenshots/dashboard-overview.png"
CANON = f"{settings.BASE_PATH}/v1/customer-success/screenshots/dashboard-overview"


# --------------------------------------------------------------------------- #
# Pure-function unit tests                                                     #
# --------------------------------------------------------------------------- #
def test_screenshot_id_extraction():
    assert screenshot_id_from_url(STALE) == "dashboard-overview"
    assert screenshot_id_from_url("https://x/dash.png") == "dash"
    assert screenshot_id_from_url(f"{CANON}?v=2") == "dashboard-overview"


def test_canonical_url_transform():
    assert canonical_url(STALE) == CANON
    assert is_canonical(CANON) is True
    assert is_canonical(STALE) is False


def test_classify_flags_stale_and_png_and_base_path():
    ok, flags, cause = classify(STALE)
    assert ok is False
    assert "stale_reference" in flags
    assert "old_png" in flags
    assert "wrong_base_path" in flags
    assert cause

    ok2, flags2, _ = classify(CANON)
    assert ok2 is True
    assert flags2 == []


# --------------------------------------------------------------------------- #
# API integration tests                                                       #
# --------------------------------------------------------------------------- #
async def _create_article(client, token, url):
    body = {
        "title": "Dashboard Guide",
        "category_key": "getting-started",
        "content": "# Dashboard\n\nWelcome.",
        "summary": "Intro",
        "tags": ["module:dashboard"],
        "screenshots": [{"url": url, "caption": "dashboard overview", "module": "dashboard"}],
    }
    return await client.post("/v1/docs/articles", headers=H(token), json=body)


async def test_verify_detects_broken_then_repair_fixes(client):
    _, t = await create_authenticated_user(client, email="imgv1@e.com", username="imgv1")
    token = t["access_token"]
    r = await _create_article(client, token, STALE)
    assert r.status_code == 201, r.text
    article_id = r.json()["id"]

    # Verify detects the broken/stale image.
    rep = (await client.get("/v1/docs/image-rendering", headers=H(token))).json()
    assert rep["report"]["images_broken"] >= 1
    assert rep["report"]["stale_references"] >= 1
    assert rep["report"]["wrong_base_path"] >= 1
    assert rep["summary"]["all_render"] is False
    broken = [b for b in rep["broken"] if b["article_id"] == article_id]
    assert broken
    assert broken[0]["stored_url"] == STALE
    assert broken[0]["expected_url"] == CANON
    assert broken[0]["root_cause"]

    # Repair rewrites the stored URL.
    fix = (await client.post("/v1/docs/image-rendering/repair", headers=H(token))).json()
    assert fix["articles_updated"] >= 1
    assert fix["images_fixed"] >= 1

    # Re-verify: everything renders, nothing stale.
    rep2 = (await client.get("/v1/docs/image-rendering", headers=H(token))).json()
    assert rep2["report"]["images_broken"] == 0
    assert rep2["report"]["stale_references"] == 0
    assert rep2["summary"]["all_render"] is True
    assert rep2["summary"]["canonical_prefix"] == CANON_PREFIX

    # Stored article URL is now canonical.
    detail = (await client.get(f"/v1/docs/articles/{article_id}", headers=H(token))).json()
    assert detail["screenshots"][0]["url"] == CANON


async def test_canonical_article_is_not_flagged(client):
    _, t = await create_authenticated_user(client, email="imgv2@e.com", username="imgv2")
    token = t["access_token"]
    r = await _create_article(client, token, CANON)
    assert r.status_code == 201, r.text

    rep = (await client.get("/v1/docs/image-rendering", headers=H(token))).json()
    assert rep["report"]["images_broken"] == 0
    assert rep["summary"]["all_render"] is True
