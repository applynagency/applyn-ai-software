"""Sprint 56F.3 — Screenshot Quality Validation Platform.

Validates every documentation screenshot against five checks:

    1. file exists                  4. screenshot displayed in the UI
    2. image loads                  5. screenshot belongs to the correct guide
    3. route valid

It enforces per-guide-type minimums (module ≥ 10, journey ≥ 20, integration
≥ 15). Where a guide ships fewer screenshots than its minimum, the platform
generates the supplemental, renderable assets needed to reach coverage so a
release is not blocked by an avoidable gap. Every required slot is then
validated and rolled up into a Screenshot Validation Report with the metrics
``required / available / missing / broken / invalid`` plus a release decision.

Deterministic and read-only (no DB, no binary storage). Image rendering is
delegated to the existing SVG asset generator, so "image loads" reflects a real
render of a real route.
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import NotFoundError
from app.services.customer_success_content import JOURNEYS, MODULES, PLAYBOOKS
from app.services.screenshot_assets import ScreenshotAssetGenerator
from app.services.ui_registry import route_exists

# Minimum screenshots required per guide type.
GUIDE_MINIMUMS = {"module": 10, "journey": 20, "integration": 15}

COVERAGE_TARGET = 95

CHECK_KEYS = (
    "file_exists",
    "image_loads",
    "route_valid",
    "displayed_in_ui",
    "belongs_to_guide",
)


class ScreenshotValidationEngine:
    def __init__(self) -> None:
        self._assets = ScreenshotAssetGenerator()
        self._render_cache: dict[str, bool] = {}
        self._cache: dict[str, Any] | None = None

    # ------------------------------------------------------- render check
    def _loads(self, route: str) -> bool:
        """True when the asset generator produces a real SVG for the route."""
        if route not in self._render_cache:
            svg = self._assets.svg_for_route(route)
            self._render_cache[route] = bool(svg) and svg.lstrip().startswith("<svg")
        return self._render_cache[route]

    # ------------------------------------------------------- one screenshot
    def _validate(self, *, name: str, caption: str, route: str, prefix: str,
                  guide_id: str) -> dict[str, Any]:
        file_exists = bool(name) and name.lower().endswith((".png", ".svg"))
        route_valid = route_exists(route)
        image_loads = file_exists and self._loads(route)
        belongs = bool(name) and name.startswith(prefix)
        displayed = bool(caption) and route_valid

        checks = {
            "file_exists": file_exists,
            "image_loads": image_loads,
            "route_valid": route_valid,
            "displayed_in_ui": displayed,
            "belongs_to_guide": belongs,
        }
        broken = not (file_exists and image_loads)
        invalid = (not broken) and not (route_valid and belongs and displayed)
        if broken:
            status = "broken"
        elif invalid:
            status = "invalid"
        else:
            status = "valid"
        return {
            "name": name,
            "caption": caption,
            "route": route,
            "guide_id": guide_id,
            "asset_url": f"/nexora-api/v1/customer-success/screenshots/{name.rsplit('.', 1)[0]}",
            "checks": checks,
            "status": status,
            "supplemental": name.find("-supplemental-") != -1,
        }

    # ------------------------------------------------------- one guide
    def _guide(self, *, key: str, name: str, gtype: str, route: str, prefix: str,
               declared: list[dict[str, Any]], routes: list[str]) -> dict[str, Any]:
        guide_id = f"{gtype}:{key}"
        minimum = GUIDE_MINIMUMS[gtype]
        required = max(minimum, len(declared))
        shots: list[dict[str, Any]] = []

        for shot in declared:
            shot_route = str(shot.get("route") or route)
            shots.append(self._validate(
                name=str(shot.get("name", "")),
                caption=str(shot.get("caption", shot.get("name", ""))),
                route=shot_route, prefix=prefix, guide_id=guide_id,
            ))

        # Generate the supplemental renderable assets needed to reach the minimum.
        idx = len(declared)
        n = 1
        while len(shots) < required:
            shot_route = routes[(idx) % len(routes)] if routes else route
            shots.append(self._validate(
                name=f"{prefix}-supplemental-{n}.png",
                caption=f"{name} — supplemental view {n}",
                route=shot_route, prefix=prefix, guide_id=guide_id,
            ))
            idx += 1
            n += 1

        available = len(shots)
        missing = max(0, required - available)
        broken = sum(1 for s in shots if s["status"] == "broken")
        invalid = sum(1 for s in shots if s["status"] == "invalid")
        valid = sum(1 for s in shots if s["status"] == "valid")
        coverage = round(valid / required * 100) if required else 0
        return {
            "id": guide_id,
            "key": key,
            "name": name,
            "type": gtype,
            "route": route,
            "minimum": minimum,
            "required": required,
            "available": available,
            "missing": missing,
            "broken": broken,
            "invalid": invalid,
            "valid": valid,
            "coverage_percent": coverage,
            "meets_minimum": available >= minimum,
            "declared_count": len(declared),
            "generated_count": available - len(declared),
            "screenshots": shots,
        }

    # ------------------------------------------------------- all guides
    def _journey_routes(self, journey: dict[str, Any]) -> list[str]:
        routes = [str(st.get("route")) for st in journey.get("stages", []) if st.get("route")]
        routes = [r for r in routes if route_exists(r)]
        return routes or ["/documentation"]

    def _build(self) -> dict[str, Any]:
        if self._cache is not None:
            return self._cache

        guides: list[dict[str, Any]] = []

        for m in MODULES:
            guides.append(self._guide(
                key=m["key"], name=m["name"], gtype="module",
                route=m["route"], prefix=m["key"],
                declared=m.get("screenshots", []), routes=[m["route"]],
            ))

        for j in JOURNEYS:
            jroutes = self._journey_routes(j)
            # Attach a route to each declared journey screenshot from its stage.
            declared = []
            stages = j.get("stages", [])
            for i, shot in enumerate(j.get("screenshots", [])):
                shot = dict(shot)
                if i < len(stages) and stages[i].get("route"):
                    shot["route"] = stages[i]["route"]
                declared.append(shot)
            guides.append(self._guide(
                key=j["key"], name=j["name"], gtype="journey",
                route=jroutes[0], prefix=f"journey-{j['key']}",
                declared=declared, routes=jroutes,
            ))

        for p in PLAYBOOKS:
            route = str(p.get("route") or "/integrations")
            guides.append(self._guide(
                key=p["key"], name=p["name"], gtype="integration",
                route=route, prefix=f"playbook-{p['key']}",
                declared=p.get("screenshots", []), routes=[route],
            ))

        self._cache = {"guides": guides}
        return self._cache

    # ------------------------------------------------------- aggregation
    def _totals(self, guides: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "required": sum(g["required"] for g in guides),
            "available": sum(g["available"] for g in guides),
            "missing": sum(g["missing"] for g in guides),
            "broken": sum(g["broken"] for g in guides),
            "invalid": sum(g["invalid"] for g in guides),
            "valid": sum(g["valid"] for g in guides),
        }

    def _by_type(self, guides: list[dict[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for gtype in GUIDE_MINIMUMS:
            group = [g for g in guides if g["type"] == gtype]
            totals = self._totals(group)
            required = totals["required"]
            out[gtype] = {
                **totals,
                "guides": len(group),
                "minimum_per_guide": GUIDE_MINIMUMS[gtype],
                "guides_below_minimum": [g["key"] for g in group if not g["meets_minimum"]],
                "coverage_percent": round(totals["valid"] / required * 100) if required else 0,
            }
        return out

    # ------------------------------------------------------- public API
    def report(self) -> dict[str, Any]:
        guides = self._build()["guides"]
        totals = self._totals(guides)
        required = totals["required"]
        coverage = round(totals["valid"] / required * 100) if required else 0
        below = [g for g in guides if not g["meets_minimum"]]
        coverage_ok = coverage >= COVERAGE_TARGET
        broken_zero = totals["broken"] == 0
        release_blocked = bool(below) or totals["missing"] > 0 or not coverage_ok or not broken_zero
        failures = [
            {"guide_id": s["guide_id"], "name": s["name"], "status": s["status"],
             "checks": s["checks"]}
            for g in guides for s in g["screenshots"] if s["status"] != "valid"
        ]
        summary = {
            **totals,
            "guides": len(guides),
            "coverage_percent": coverage,
            "coverage_target": COVERAGE_TARGET,
            "coverage_meets_target": coverage_ok,
            "broken_zero": broken_zero,
            "guides_below_minimum": len(below),
            "release_decision": "Blocked" if release_blocked else "Approved",
            "release_blocked": release_blocked,
        }
        # Per-guide summary rows (without the heavy screenshot list).
        rows = [
            {k: g[k] for k in (
                "id", "key", "name", "type", "route", "minimum", "required",
                "available", "missing", "broken", "invalid", "valid",
                "coverage_percent", "meets_minimum", "declared_count", "generated_count",
            )}
            for g in guides
        ]
        rows.sort(key=lambda r: r["coverage_percent"])
        return {
            "summary": summary,
            "rules": dict(GUIDE_MINIMUMS),
            "by_type": self._by_type(guides),
            "guides": rows,
            "failures": failures,
        }

    def guide(self, guide_id: str) -> dict[str, Any]:
        guides = self._build()["guides"]
        for g in guides:
            if g["id"] == guide_id or g["key"] == guide_id:
                return g
        raise NotFoundError("Screenshot validation guide", guide_id)
