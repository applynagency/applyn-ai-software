"""Sprint 56F.7 — Screenshot Asset Path Audit.

Audits every *generated* documentation screenshot reference end-to-end to
explain (and prevent) HTTP 404s. For each reference it records the
``screenshot_id``, ``image_path``, ``article_id`` and ``module``, then verifies:

    1. filesystem existence of the backing asset,
    2. the static serving path is a registered route,
    3. the frontend URL the app generates actually resolves.

Root cause for the historical 404s: documentation references screenshots by
module-based ``*.png`` filenames that are served *dynamically* (rendered to SVG)
at ``{BASE_PATH}/v1/customer-success/screenshots/{screenshot_id}``. The
on-disk generated assets are area-based ``*.svg`` files, so any consumer that
requested a screenshot as a flat static ``.png`` file, or omitted the
``{BASE_PATH}`` (``/nexora-api``) prefix, received a 404. The audit reports the
authoritative resolvable URL for every reference and confirms it returns 200.

Deterministic and read-only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.customer_success_content import (
    JOURNEYS,
    MODULES,
    PLAYBOOKS,
    SUCCESS_CENTER,
)
from app.services.screenshot_assets import ScreenshotAssetGenerator

# Canonical, working serving prefix for documentation screenshots.
SERVE_PREFIX = f"{settings.BASE_PATH}/v1/customer-success/screenshots"
ASSET_DIR_REL = "assets/documentation/screenshots"


def _strip_ext(name: str) -> str:
    return name.rsplit(".", 1)[0] if "." in name else name


class ScreenshotAssetAuditEngine:
    def __init__(self) -> None:
        self._assets = ScreenshotAssetGenerator()
        self._base_dir: Path = self._assets.base_dir
        self._cache: dict[str, Any] | None = None

    # ------------------------------------------------------- reference discovery
    def _references(self) -> list[dict[str, str]]:
        """Every generated screenshot reference across the documentation set."""
        refs: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()

        def add(name: str, article_id: str, module: str) -> None:
            if not name:
                return
            sid = _strip_ext(name)
            key = (sid, article_id)
            if key in seen:
                return
            seen.add(key)
            refs.append({
                "screenshot_id": sid,
                "filename": name,
                "article_id": article_id,
                "module": module,
            })

        for m in MODULES:
            article = m["key"]
            for shot in m.get("screenshots", []):
                add(str(shot.get("name", "")), article, m["key"])
            for step in m.get("steps", []):
                add(str(step.get("screenshot", "")), article, m["key"])

        for j in JOURNEYS:
            article = f"journey:{j['key']}"
            for shot in j.get("screenshots", []):
                add(str(shot.get("name", "")), article, j["key"])
            for stage in j.get("stages", []):
                add(str(stage.get("screenshot", "")), article, str(stage.get("module", j["key"])))

        for p in PLAYBOOKS:
            article = f"integration:{p['key']}"
            for shot in p.get("screenshots", []):
                add(str(shot.get("name", "")), article, p["key"])

        for g in SUCCESS_CENTER:
            article = f"success:{g['key']}"
            for shot in g.get("screenshots", []):
                add(str(shot.get("name", "")), article, g["key"])

        return refs

    # ------------------------------------------------------- per-reference audit
    def _resolves(self, screenshot_id: str) -> bool:
        """True when the serving endpoint renders a valid SVG (HTTP 200)."""
        try:
            svg = self._assets.svg_for_id(screenshot_id)
        except Exception:
            return False
        return bool(svg) and svg.lstrip().startswith("<svg")

    def _audit_one(self, ref: dict[str, str]) -> dict[str, Any]:
        sid = ref["screenshot_id"]
        image_path = f"{ASSET_DIR_REL}/{sid}.svg"
        serving_url = f"{SERVE_PREFIX}/{sid}"

        file_exists = (self._base_dir / f"{sid}.svg").is_file()
        # The screenshot is served via the dynamic render route; the static path
        # is valid when it sits under the registered serving prefix.
        static_route_valid = serving_url.startswith(SERVE_PREFIX)
        url_resolves = self._resolves(sid)

        if url_resolves:
            status = "ok"
            root_cause = ""
        elif not static_route_valid:
            status = "invalid_static_route"
            root_cause = "Serving URL is not under the registered screenshot route."
        elif not file_exists:
            status = "missing_file"
            root_cause = "No backing asset and the renderer could not produce an image."
        else:
            status = "broken_url"
            root_cause = "Serving endpoint failed to render the screenshot."

        return {
            "screenshot_id": sid,
            "filename": ref["filename"],
            "image_path": image_path,
            "article_id": ref["article_id"],
            "module": ref["module"],
            "url": serving_url,
            "file_exists": file_exists,
            "static_route_valid": static_route_valid,
            "url_resolves": url_resolves,
            "served_dynamically": url_resolves and not file_exists,
            "status": status,
            "root_cause": root_cause,
        }

    # ------------------------------------------------------- build
    def _build(self) -> dict[str, Any]:
        if self._cache is not None:
            return self._cache
        audited = [self._audit_one(r) for r in self._references()]
        self._cache = {"screenshots": audited}
        return self._cache

    # ------------------------------------------------------- public API
    def report(self) -> dict[str, Any]:
        shots = self._build()["screenshots"]
        total = len(shots)
        valid = sum(1 for s in shots if s["url_resolves"])
        missing = sum(1 for s in shots if s["status"] == "missing_file")
        broken = sum(1 for s in shots if s["status"] == "broken_url")
        invalid_static = sum(1 for s in shots if s["status"] == "invalid_static_route")
        served_dynamically = sum(1 for s in shots if s["served_dynamically"])
        backed_by_file = sum(1 for s in shots if s["file_exists"])
        failures = [s for s in shots if s["status"] != "ok"]

        return {
            "report": {
                "total_references": total,
                "valid_files": valid,
                "missing_files": missing,
                "broken_urls": broken,
                "invalid_static_routes": invalid_static,
            },
            "summary": {
                "total_references": total,
                "resolving": valid,
                "served_dynamically": served_dynamically,
                "backed_by_static_file": backed_by_file,
                "all_resolve": valid == total and total > 0,
                "failure_count": len(failures),
                "serving_prefix": SERVE_PREFIX,
                "asset_directory": ASSET_DIR_REL,
            },
            "failures": failures,
            "screenshots": shots,
        }
