"""Sprint 56B — ScreenshotAnnotationService.

Stores annotation *metadata* (arrows, highlights, labels, callouts) for key
screenshots. No image editing is performed — annotations are coordinate +
description metadata that a viewer can overlay on a screenshot.

Each annotation: screenshot_id, kind, target, description, region {x,y,w,h}.
"""

from __future__ import annotations

from typing import Any

from app.services.customer_success_content import MODULE_EXPECTED_SCREENS, MODULES

# Annotation kind is assigned deterministically per index so each screenshot
# shows a mix of highlights, callouts, labels, and arrows.
_KINDS = ["highlight", "callout", "label", "arrow"]

# A representative grid of regions (percent-based) so overlays never overlap.
_REGIONS = [
    {"x": 6, "y": 12, "w": 40, "h": 18},
    {"x": 54, "y": 12, "w": 40, "h": 18},
    {"x": 6, "y": 40, "w": 40, "h": 18},
    {"x": 54, "y": 40, "w": 40, "h": 18},
    {"x": 6, "y": 68, "w": 40, "h": 18},
    {"x": 54, "y": 68, "w": 40, "h": 18},
]


def _annotations_for(screenshot_id: str, targets: list[str]) -> list[dict[str, Any]]:
    out = []
    for i, target in enumerate(targets):
        out.append({
            "screenshot_id": screenshot_id,
            "kind": _KINDS[i % len(_KINDS)],
            "target": target,
            "description": f"{target} — review this area to confirm the expected result.",
            "region": _REGIONS[i % len(_REGIONS)],
        })
    return out


class ScreenshotAnnotationService:
    def _catalog(self) -> dict[str, list[dict[str, Any]]]:
        """screenshot_id -> annotations. Overview + results shots of every module
        are annotated with that module's key expected screens/widgets."""
        catalog: dict[str, list[dict[str, Any]]] = {}
        for m in MODULES:
            key = m["key"]
            targets = MODULE_EXPECTED_SCREENS.get(key, [])
            if not targets:
                continue
            for shot in (f"{key}-overview", f"{key}-results"):
                catalog[shot] = _annotations_for(shot, targets)
        return catalog

    def list(self, *, screenshot_id: str | None = None) -> list[dict[str, Any]]:
        catalog = self._catalog()
        if screenshot_id:
            return catalog.get(screenshot_id, [])
        out: list[dict[str, Any]] = []
        for anns in catalog.values():
            out.extend(anns)
        return out

    def get(self, screenshot_id: str) -> dict[str, Any]:
        anns = self.list(screenshot_id=screenshot_id)
        return {"screenshot_id": screenshot_id, "annotations": anns, "total": len(anns)}

    def summary(self) -> dict[str, Any]:
        catalog = self._catalog()
        total = sum(len(v) for v in catalog.values())
        by_kind: dict[str, int] = {k: 0 for k in _KINDS}
        for anns in catalog.values():
            for a in anns:
                by_kind[a["kind"]] = by_kind.get(a["kind"], 0) + 1
        return {
            "annotated_screenshots": len(catalog),
            "total_annotations": total,
            "by_kind": by_kind,
            "kinds": _KINDS,
        }
