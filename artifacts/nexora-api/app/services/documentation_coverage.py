"""Sprint 56A.1 — DocumentationCoverageDashboard + readiness report.

Combines the documentation quality engine with the screenshot coverage system to
produce a per-module dashboard and a platform-wide documentation readiness report.
Read-only and deterministic.
"""

from __future__ import annotations

from typing import Any

from app.services.customer_success_content import (
    JOURNEYS,
    LAST_UPDATED,
    MODULES,
    PLAYBOOKS,
    SUCCESS_CENTER,
)
from app.services.documentation_quality import DocumentationQualityService
from app.services.screenshot_coverage import ScreenshotCoverageService


def _guide_count(module_key: str) -> int:
    count = 1  # the module guide itself
    count += sum(1 for s in SUCCESS_CENTER if module_key in (s.get("related") or []))
    count += sum(
        1 for j in JOURNEYS if any(stage.get("module") == module_key for stage in j["stages"])
    )
    return count


class DocumentationCoverageDashboard:
    def __init__(self) -> None:
        self.quality = DocumentationQualityService()
        self.coverage = ScreenshotCoverageService()

    def dashboard(self) -> dict[str, Any]:
        report = self.quality.report()
        score_by_key = {m["key"]: m["coverage_score"] for m in report["modules"]}
        level_by_key = {m["key"]: m["level"] for m in report["modules"]}
        shot_by_key = self.coverage.module_coverage_percent()
        rows = []
        for m in MODULES:
            rows.append(
                {
                    "module": m["key"],
                    "name": m["name"],
                    "category": m["category"],
                    "coverage_score": score_by_key.get(m["key"], 0),
                    "quality_level": level_by_key.get(m["key"], "Poor"),
                    "screenshot_coverage": shot_by_key.get(m["key"], 0),
                    "guide_count": _guide_count(m["key"]),
                    "last_updated": m.get("updated_at", LAST_UPDATED),
                }
            )
        return {
            "modules": rows,
            "average_score": report["average_score"],
            "passes_target": report["passes_target"],
            "target": report["target"],
        }

    def readiness(self) -> dict[str, Any]:
        report = self.quality.report()
        platform = self.coverage.platform()
        modules_ready = report["production_ready_count"]
        modules_total = report["modules_total"]
        # Journeys are "ready" when their tracked screenshots are at least "Good".
        journey_metrics = self.coverage.metrics()["by_journey"]
        journeys_ready = sum(1 for j in journey_metrics if j["coverage_percent"] >= 76)
        integrations_ready = sum(1 for p in PLAYBOOKS if p.get("validation_checklist"))
        documentation_score = report["average_score"]
        screenshot_coverage = platform["coverage_percent"]
        release_ready = (
            documentation_score >= 95
            and screenshot_coverage >= 90
            and modules_ready == modules_total
            and journeys_ready == len(JOURNEYS)
            and integrations_ready == len(PLAYBOOKS)
        )
        return {
            "documentation_score": documentation_score,
            "screenshot_coverage": screenshot_coverage,
            "modules_ready": modules_ready,
            "modules_total": modules_total,
            "journeys_ready": journeys_ready,
            "journeys_total": len(JOURNEYS),
            "integrations_ready": integrations_ready,
            "integrations_total": len(PLAYBOOKS),
            "release_ready": release_ready,
        }
