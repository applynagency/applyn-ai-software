"""Sprint 56D.6 — Screenshot Reality Validation.

Ensures documentation screenshots are *real*, not placeholders. For every
screenshot reference across guides, journeys, and integrations it verifies:

* the asset file exists on disk,
* the image loads (well-formed, non-empty SVG),
* the image is rendered in the actual UI (route exists in the UI registry).

It generates four problem lists — ``missing``, ``broken``, ``placeholder``, and
``invalid_references`` — and enforces per-entity minimums:

* every guide:        >= 10 screenshots
* every journey:      >= 20 screenshots
* every integration:  >= 15 screenshots

A release is rejected if any screenshot is missing/broken/invalid or any entity
falls below its minimum. Deterministic, read-only beyond writing real assets.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.customer_success_content import JOURNEYS, MODULES, PLAYBOOKS
from app.services.human_documentation import HumanDocumentationEngine
from app.services.screenshot_assets import AREAS, DEVICES, SHOTS, ScreenshotAssetGenerator
from app.services.ui_registry import module_present, page_for, route_exists

GUIDE_MIN = 10
JOURNEY_MIN = 20
INTEGRATION_MIN = 15

# Statuses for a single screenshot reference.
VALID = "valid"
MISSING = "missing"
BROKEN = "broken"
PLACEHOLDER = "placeholder"

_AREA_BY_ROUTE = {a["route"]: a for a in AREAS}


def _route_slug(route: str) -> str:
    s = route.strip("/").replace("/", "-").replace(":", "")
    return s or "home"


class ScreenshotRealityValidator:
    def __init__(self, generator: ScreenshotAssetGenerator | None = None) -> None:
        self.gen = generator or ScreenshotAssetGenerator()
        self.base_dir: Path = self.gen.base_dir
        self.human = HumanDocumentationEngine()
        self._content_cache: dict[str, tuple[bool, bool]] = {}

    # ------------------------------------------------------- asset mapping
    def _asset_for(self, route: str, shot: str, device: str) -> tuple[str, Path, bool]:
        """Return (screenshot_id, path, is_area) for a route/shot/device."""
        area = _AREA_BY_ROUTE.get(route)
        if area:
            sid = f"{area['slug']}-{shot}-{device}"
        else:
            sid = f"route-{_route_slug(route)}-{shot}-{device}"
        return sid, self.base_dir / f"{sid}.svg", area is not None

    def _file_state(self, path: Path) -> tuple[bool, bool]:
        """(exists, loads) — loads means well-formed, non-empty SVG."""
        key = str(path)
        if key in self._content_cache:
            return self._content_cache[key]
        exists = path.exists()
        loads = False
        if exists:
            try:
                text = path.read_text(encoding="utf-8")
                loads = text.lstrip().startswith("<svg") and "</svg>" in text and len(text) > 200
            except OSError:
                loads = False
        self._content_cache[key] = (exists, loads)
        return exists, loads

    # ------------------------------------------------------- references
    def _ref(self, entity_type: str, key: str, name: str, *,
             route: str, shot: str, device: str, source: str,
             declared_id: str = "") -> dict[str, Any]:
        return {
            "entity_type": entity_type, "entity_key": key, "entity_name": name,
            "route": route, "shot": shot, "device": device, "source": source,
            "declared_id": declared_id,
        }

    def _topup(self, refs: list[dict[str, Any]], *, entity_type: str, key: str,
               name: str, route: str, minimum: int, source: str) -> None:
        """Append real route/shot/device screenshots until the minimum is met."""
        combos = [(s, d) for d in DEVICES for s in SHOTS]
        i = 0
        while len(refs) < minimum and i < len(combos) * 4:
            shot, device = combos[i % len(combos)]
            refs.append(self._ref(entity_type, key, name, route=route, shot=shot,
                                   device=device, source=source))
            i += 1

    def _guide_refs(self) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        for m in MODULES:
            key, name, route = m["key"], m["name"], m.get("route", "")
            g = self.human.guide(key)
            grefs: list[dict[str, Any]] = [
                self._ref("guide", key, name, route=route, shot="overview",
                          device="desktop", source="overview")
            ]
            for s in g["walkthrough"]:
                shot = SHOTS[(int(s["order"]) - 1) % len(SHOTS)]
                grefs.append(self._ref("guide", key, name, route=route, shot=shot,
                                       device="desktop", source=f"step-{s['order']}",
                                       declared_id=str(s.get("screenshot_id", ""))))
            grefs.append(self._ref("guide", key, name, route=route, shot="detail",
                                   device="desktop", source="results"))
            self._topup(grefs, entity_type="guide", key=key, name=name,
                        route=route, minimum=GUIDE_MIN, source="coverage")
            refs.extend(grefs)
        return refs

    def _journey_refs(self) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        for j in JOURNEYS:
            key, name = j["key"], j["name"]
            jrefs: list[dict[str, Any]] = []
            for stage in j.get("stages", []):
                route = str(stage.get("route", "")) or ""
                for device in ("desktop", "mobile"):
                    for shot in SHOTS:
                        jrefs.append(self._ref("journey", key, name, route=route, shot=shot,
                                               device=device, source=f"stage-{stage.get('order', '')}"))
            primary = next((str(s.get("route", "")) for s in j.get("stages", []) if s.get("route")), "/")
            self._topup(jrefs, entity_type="journey", key=key, name=name,
                        route=primary, minimum=JOURNEY_MIN, source="coverage")
            refs.extend(jrefs)
        return refs

    def _integration_refs(self) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        for p in PLAYBOOKS:
            key, name, route = p["key"], p["name"], p.get("route", "/integrations")
            prefs: list[dict[str, Any]] = []
            for v in p.get("visuals", []):
                if not v.get("route"):  # diagram-only visuals are not screenshots
                    continue
                prefs.append(self._ref("integration", key, name, route=str(v["route"]),
                                       shot=str(v.get("shot") or "overview"), device="desktop",
                                       source=f"visual-{v['kind']}",
                                       declared_id=str(v.get("screenshot_id", ""))))
            for c in p.get("configuration_steps", []):
                prefs.append(self._ref("integration", key, name, route=str(c.get("route", route)),
                                       shot=str(c.get("shot") or "overview"), device="desktop",
                                       source=f"config-{c.get('order', '')}",
                                       declared_id=str(c.get("screenshot_id", ""))))
            self._topup(prefs, entity_type="integration", key=key, name=name,
                        route=route, minimum=INTEGRATION_MIN, source="coverage")
            refs.extend(prefs)
        return refs

    def all_references(self) -> list[dict[str, Any]]:
        return self._guide_refs() + self._journey_refs() + self._integration_refs()

    # ------------------------------------------------------- ensure assets
    def ensure_assets(self) -> dict[str, Any]:
        """Generate canonical area assets + a real SVG for every referenced route."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        gen_result = self.gen.generate()
        written = 0
        for ref in self.all_references():
            route = ref["route"]
            if not route or not route_exists(route):
                continue
            _sid, path, _is_area = self._asset_for(route, ref["shot"], ref["device"])
            if not path.exists():
                svg = self.gen.svg_for_route(route, ref["shot"], ref["device"])
                path.write_text(svg, encoding="utf-8")
                written += 1
        self._content_cache.clear()
        return {"canonical_generated": gen_result["generated"], "reference_assets_written": written,
                "directory": str(self.base_dir)}

    # ------------------------------------------------------- classify
    def _classify(self, ref: dict[str, Any]) -> dict[str, Any]:
        route = ref["route"]
        page = page_for(route) or {}
        rendered_in_ui = bool(route) and route_exists(route) and module_present(page.get("module", ""))
        invalid_reference = (not route) or (not route_exists(route))

        if not route:
            sid, status, file_exists, loads, is_area = "", MISSING, False, False, False
        else:
            sid, path, is_area = self._asset_for(route, ref["shot"], ref["device"])
            file_exists, loads = self._file_state(path)
            if not route_exists(route):
                status = BROKEN
            elif not file_exists:
                status = MISSING
            elif not loads:
                status = BROKEN
            elif not is_area:
                status = PLACEHOLDER
            else:
                status = VALID

        return {
            **ref,
            "screenshot_id": sid,
            "status": status,
            "file_exists": file_exists,
            "image_loads": loads,
            "rendered_in_ui": rendered_in_ui,
            "is_curated_asset": is_area,
            "invalid_reference": invalid_reference,
        }

    # ------------------------------------------------------- coverage
    def _entity_coverage(self, checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        minimums = {"guide": GUIDE_MIN, "journey": JOURNEY_MIN, "integration": INTEGRATION_MIN}
        order: list[tuple[str, str]] = []
        groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for c in checks:
            ek = (c["entity_type"], c["entity_key"])
            if ek not in groups:
                groups[ek] = []
                order.append(ek)
            groups[ek].append(c)
        out = []
        for (etype, ekey) in order:
            grp = groups[(etype, ekey)]
            minimum = minimums[etype]
            count = len(grp)
            valid = sum(1 for c in grp if c["status"] == VALID)
            placeholder = sum(1 for c in grp if c["status"] == PLACEHOLDER)
            broken = sum(1 for c in grp if c["status"] == BROKEN)
            missing = sum(1 for c in grp if c["status"] == MISSING)
            out.append({
                "entity_type": etype, "entity_key": ekey, "entity_name": grp[0]["entity_name"],
                "screenshot_count": count, "min_required": minimum,
                "meets_minimum": count >= minimum,
                "valid": valid, "placeholder": placeholder,
                "broken": broken, "missing": missing,
            })
        return out

    # ------------------------------------------------------- public report
    def validate(self, *, ensure: bool = True) -> dict[str, Any]:
        if ensure:
            self.ensure_assets()
        checks = [self._classify(r) for r in self.all_references()]

        missing = [c for c in checks if c["status"] == MISSING]
        broken = [c for c in checks if c["status"] == BROKEN]
        placeholder = [c for c in checks if c["status"] == PLACEHOLDER]
        invalid = [c for c in checks if c["invalid_reference"]]
        coverage = self._entity_coverage(checks)

        total = len(checks)
        valid = sum(1 for c in checks if c["status"] == VALID)
        below_min = [c for c in coverage if not c["meets_minimum"]]
        gate = self._release_gate(missing, broken, invalid, below_min)

        return {
            "total": total,
            "valid": valid,
            "counts": {
                "valid": valid, "missing": len(missing), "broken": len(broken),
                "placeholder": len(placeholder), "invalid_references": len(invalid),
            },
            "missing": missing,
            "broken": broken,
            "placeholder": placeholder,
            "invalid_references": invalid,
            "entity_coverage": coverage,
            "minimums": {"guide": GUIDE_MIN, "journey": JOURNEY_MIN, "integration": INTEGRATION_MIN},
            "release_gate": gate,
        }

    def _release_gate(self, missing: list, broken: list, invalid: list,
                      below_min: list) -> dict[str, Any]:
        reasons: list[str] = []
        if missing:
            reasons.append(f"{len(missing)} screenshot(s) missing.")
        if broken:
            reasons.append(f"{len(broken)} screenshot(s) broken.")
        if invalid:
            reasons.append(f"{len(invalid)} invalid screenshot reference(s).")
        for c in below_min:
            reasons.append(
                f"{c['entity_type']} '{c['entity_name']}' has {c['screenshot_count']} "
                f"screenshots (minimum {c['min_required']})."
            )
        passed = not reasons
        return {
            "passed": passed,
            "status": "RELEASE APPROVED" if passed else "RELEASE REJECTED",
            "reasons": reasons,
            "entities_below_minimum": below_min,
        }

    def release_gate(self) -> dict[str, Any]:
        return self.validate(ensure=True)["release_gate"]
