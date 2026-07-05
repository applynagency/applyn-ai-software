"""Tests for optimized static-asset serving (caching + compression)."""

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.web import static_assets as sa

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"
DIST_DIR = STATIC_DIR / "dist"


# --------------------------- pure helper unit tests ---------------------------

def test_is_safe_asset_name():
    assert sa.is_safe_asset_name("app.3f9cc201ce.js")
    assert sa.is_safe_asset_name("styles.12bc785740.css")
    assert not sa.is_safe_asset_name("")
    assert not sa.is_safe_asset_name("../secret.env")
    assert not sa.is_safe_asset_name("dir/app.js")
    assert not sa.is_safe_asset_name("a\\b.js")
    assert not sa.is_safe_asset_name("..")


def test_media_type_strips_precompression_suffix():
    assert sa.media_type_for("app.x.js").startswith("text/javascript")
    assert sa.media_type_for("app.x.js.br").startswith("text/javascript")
    assert sa.media_type_for("app.x.js.gz").startswith("text/javascript")
    assert sa.media_type_for("styles.x.css.gz").startswith("text/css")
    assert sa.media_type_for("data.x.json") == "application/json"
    assert sa.media_type_for("mystery.bin") == "application/octet-stream"


def test_parse_accept_encoding_honours_q_values():
    assert sa.parse_accept_encoding(None) == set()
    assert sa.parse_accept_encoding("gzip, br") == {"gzip", "br"}
    assert "gzip" not in sa.parse_accept_encoding("gzip;q=0, br")
    assert "br" in sa.parse_accept_encoding("br;q=1.0")
    assert "*" in sa.parse_accept_encoding("*")


def test_choose_encoding_prefers_brotli():
    assert sa.choose_encoding("gzip, br", {"br", "gzip"}) == "br"
    assert sa.choose_encoding("gzip", {"br", "gzip"}) == "gzip"
    # brotli requested but not available -> fall back to gzip
    assert sa.choose_encoding("gzip, br", {"gzip"}) == "gzip"
    # identity / none
    assert sa.choose_encoding("identity", {"br", "gzip"}) is None
    assert sa.choose_encoding(None, {"br"}) is None
    # explicit rejection
    assert sa.choose_encoding("br;q=0, gzip", {"br", "gzip"}) == "gzip"
    # wildcard
    assert sa.choose_encoding("*", {"br", "gzip"}) == "br"


def test_encoding_suffix():
    assert sa.encoding_suffix("br") == ".br"
    assert sa.encoding_suffix("gzip") == ".gz"
    assert sa.encoding_suffix(None) == ""


def test_asset_headers():
    h = sa.asset_headers("br", immutable=True)
    assert h["Content-Encoding"] == "br"
    assert "immutable" in h["Cache-Control"]
    assert "max-age=31536000" in h["Cache-Control"]
    assert h["Vary"] == "Accept-Encoding"

    h2 = sa.asset_headers(None, immutable=False)
    assert "Content-Encoding" not in h2
    assert h2["Cache-Control"] == sa.NO_CACHE


# --------------------------- integration (built dist) ---------------------------

_DIST_READY = (DIST_DIR / "manifest.json").is_file()
_needs_build = pytest.mark.skipif(
    not _DIST_READY, reason="run `npm run build` to produce static/dist"
)


def _unprefixed_client() -> AsyncClient:
    # The shared `client` fixture is scoped under the API prefix; dashboard /
    # asset routes live at the site root, so use a root-based client here.
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@_needs_build
async def test_hashed_asset_served_brotli_with_immutable_cache():
    manifest = json.loads((DIST_DIR / "manifest.json").read_text())
    filename = manifest["app.js"].replace("/assets/", "")
    async with _unprefixed_client() as ac:
        resp = await ac.get(f"/assets/{filename}", headers={"Accept-Encoding": "gzip, br"})
    assert resp.status_code == 200
    assert resp.headers["content-encoding"] == "br"
    assert "immutable" in resp.headers["cache-control"]
    assert resp.headers["vary"] == "Accept-Encoding"
    assert resp.headers["content-type"].startswith("text/javascript")


@_needs_build
async def test_hashed_asset_identity_when_no_encoding_accepted():
    manifest = json.loads((DIST_DIR / "manifest.json").read_text())
    filename = manifest["styles.css"].replace("/assets/", "")
    async with _unprefixed_client() as ac:
        resp = await ac.get(f"/assets/{filename}", headers={"Accept-Encoding": "identity"})
    assert resp.status_code == 200
    assert "content-encoding" not in resp.headers
    assert "immutable" in resp.headers["cache-control"]


@_needs_build
async def test_unknown_or_unsafe_asset_returns_404():
    async with _unprefixed_client() as ac:
        missing = await ac.get("/assets/does-not-exist.deadbeef.js")
        unsafe = await ac.get("/assets/not-a-real-name")
    assert missing.status_code == 404
    assert unsafe.status_code == 404


@_needs_build
async def test_index_html_is_no_cache():
    async with _unprefixed_client() as ac:
        resp = await ac.get("/")
    assert resp.status_code == 200
    assert "no-cache" in resp.headers["cache-control"]
    # built shell references hashed assets + inlines the manifest
    assert "/assets/app." in resp.text
    assert "__ASSETS__" in resp.text
