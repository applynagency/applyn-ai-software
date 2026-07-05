"""Helpers for serving the optimized, content-hashed frontend bundle.

The frontend build (``scripts/build-frontend.mjs``) emits content-hashed assets
plus precomputed ``.gz`` / ``.br`` variants into ``static/dist``. These pure
helpers let the API serve them with correct content negotiation and aggressive,
*safe* caching:

* Hashed assets (``/assets/...``) are immutable — the URL changes whenever the
  bytes change — so they get a one-year ``immutable`` cache.
* The HTML shell and the dev (un-hashed) files stay ``no-cache`` so deploys are
  picked up immediately.

Everything here is dependency-free and unit-tested in ``tests/test_static_assets``.
"""

from __future__ import annotations

import re

# Filenames are restricted to a conservative allowlist to prevent path
# traversal — hashed asset names only ever contain these characters.
_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")

IMMUTABLE_CACHE = "public, max-age=31536000, immutable"
NO_CACHE = "no-cache, must-revalidate"

_MEDIA_TYPES = {
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".map": "application/json",
    ".html": "text/html; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".png": "image/png",
    ".woff2": "font/woff2",
}

# Content-Encoding token -> precompressed file suffix, in server preference order.
_ENCODINGS = (("br", ".br"), ("gzip", ".gz"))


def is_safe_asset_name(filename: str) -> bool:
    """Reject empty names, separators and traversal segments."""
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        return False
    return bool(_SAFE_NAME.match(filename))


def media_type_for(filename: str) -> str:
    """Resolve the media type from the *logical* extension, ignoring a trailing
    ``.br`` / ``.gz`` precompression suffix."""
    base = filename
    for suffix in (".br", ".gz"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    dot = base.rfind(".")
    ext = base[dot:].lower() if dot != -1 else ""
    return _MEDIA_TYPES.get(ext, "application/octet-stream")


def parse_accept_encoding(header: str | None) -> set[str]:
    """Parse an ``Accept-Encoding`` header into the set of accepted encodings,
    honouring explicit ``q=0`` rejections."""
    accepted: set[str] = set()
    if not header:
        return accepted
    for part in header.split(","):
        token = part.strip()
        if not token:
            continue
        name, _, params = token.partition(";")
        name = name.strip().lower()
        if not name:
            continue
        q = 1.0
        if "q=" in params:
            try:
                q = float(params.split("q=", 1)[1].strip())
            except (ValueError, IndexError):
                q = 1.0
        if q > 0:
            accepted.add(name)
    return accepted


def choose_encoding(accept_encoding: str | None, available: set[str]) -> str | None:
    """Pick the best precompressed encoding the client accepts.

    ``available`` is the set of encodings for which a precompressed file exists.
    Brotli is preferred over gzip. Returns ``None`` for an identity response.
    """
    accepted = parse_accept_encoding(accept_encoding)
    wildcard = "*" in accepted
    for token, _suffix in _ENCODINGS:
        if token in available and (token in accepted or wildcard):
            return token
    return None


def encoding_suffix(encoding: str | None) -> str:
    """Map an encoding token to its precompressed file suffix ('' for identity)."""
    if not encoding:
        return ""
    for token, suffix in _ENCODINGS:
        if token == encoding:
            return suffix
    return ""


def asset_headers(encoding: str | None, *, immutable: bool = True) -> dict[str, str]:
    """Response headers for a static asset."""
    headers = {
        "Cache-Control": IMMUTABLE_CACHE if immutable else NO_CACHE,
        "Vary": "Accept-Encoding",
    }
    if encoding:
        headers["Content-Encoding"] = encoding
    return headers
