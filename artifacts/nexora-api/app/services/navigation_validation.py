"""Sprint 56C — NavigationValidationService.

Validates documented navigation paths (navigation maps + module routes) against
the UI registry and produces a navigation health report. Read-only.
"""

from __future__ import annotations

from typing import Any

from app.services.customer_success_content import MODULES
from app.services.ui_registry import route_exists
from app.services.visual_documentation import VisualDocumentationService


class NavigationValidationService:
    def __init__(self) -> None:
        self.visual = VisualDocumentationService()

    def _paths(self) -> list[dict[str, Any]]:
        paths: list[dict[str, Any]] = []
        # Navigation-map chains.
        for nm in self.visual.navigation_maps()["items"]:
            routes = [n["route"] for n in nm["nodes"]]
            missing = [r for r in routes if not route_exists(r)]
            paths.append({
                "name": nm["name"],
                "kind": "navigation_map",
                "routes": routes,
                "valid": not missing,
                "missing_routes": missing,
            })
        # Module landing routes.
        for m in MODULES:
            route = m["route"]
            valid = route_exists(route)
            paths.append({
                "name": m["name"],
                "kind": "module",
                "routes": [route],
                "valid": valid,
                "missing_routes": [] if valid else [route],
            })
        return paths

    def report(self) -> dict[str, Any]:
        paths = self._paths()
        total = len(paths)
        valid = sum(1 for p in paths if p["valid"])
        broken = total - valid
        return {
            "paths": paths,
            "total_paths": total,
            "valid_paths": valid,
            "broken_paths": broken,
            "health_score": round(valid / total * 100) if total else 0,
        }
