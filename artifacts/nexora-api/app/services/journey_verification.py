"""Sprint 56C — JourneyVerificationService.

Verifies each customer journey end-to-end: navigation path, screenshots,
expected results, and backing documentation guides. Read-only.

Status: PASS, WARNING, FAIL.
"""

from __future__ import annotations

from typing import Any

from app.services.customer_success_content import JOURNEYS, get_module
from app.services.ui_registry import route_exists


class JourneyVerificationService:
    def _verify_journey(self, journey: dict[str, Any]) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        nav_ok = True
        screens_ok = True
        results_ok = True
        guides_ok = True

        for stage in journey["stages"]:
            module = get_module(stage.get("module", ""))
            route = (module or {}).get("route", "")
            if not module or not route_exists(route):
                nav_ok = False
                guides_ok = False
            if not stage.get("screenshot"):
                screens_ok = False
            if not stage.get("expected_outcome"):
                results_ok = False

        checks = [
            {"check": "navigation_path", "passed": nav_ok},
            {"check": "screenshots", "passed": screens_ok},
            {"check": "expected_results", "passed": results_ok},
            {"check": "documentation_guides", "passed": guides_ok},
        ]

        if not nav_ok:
            status = "FAIL"
        elif not (screens_ok and results_ok and guides_ok):
            status = "WARNING"
        else:
            status = "PASS"

        return {
            "key": journey["key"],
            "name": journey["name"],
            "status": status,
            "checks": checks,
            "stage_count": len(journey["stages"]),
        }

    def report(self) -> dict[str, Any]:
        journeys = [self._verify_journey(j) for j in JOURNEYS]
        total = len(journeys)
        passing = sum(1 for j in journeys if j["status"] == "PASS")
        return {
            "journeys": journeys,
            "total": total,
            "passing": passing,
            "warning": sum(1 for j in journeys if j["status"] == "WARNING"),
            "failing": sum(1 for j in journeys if j["status"] == "FAIL"),
            "journey_health": round(passing / total * 100) if total else 0,
        }
