"""Sprint 56C — DocumentationReleaseGateService.

Evaluates documentation release gates and produces a release report. A release is
"ready" only when screenshot coverage, verified screenshots, navigation health,
and consistency score all meet the >=95 threshold. Read-only, deterministic.
"""

from __future__ import annotations

from typing import Any

from app.services.documentation_consistency import DocumentationConsistencyService
from app.services.documentation_verification import DocumentationVerificationService
from app.services.journey_verification import JourneyVerificationService
from app.services.navigation_validation import NavigationValidationService
from app.services.visual_documentation import VisualDocumentationService

THRESHOLD = 95


class DocumentationReleaseGateService:
    def __init__(self) -> None:
        self.verification = DocumentationVerificationService()
        self.navigation = NavigationValidationService()
        self.consistency = DocumentationConsistencyService()
        self.journey = JourneyVerificationService()
        self.visual = VisualDocumentationService()

    def metrics(self) -> dict[str, Any]:
        coverage = self.visual.coverage_dashboard()["platform"]["coverage_percent"]
        verified = self.verification.summary()["verified_percent"]
        navigation = self.navigation.report()["health_score"]
        consistency = self.consistency.report()["consistency_score"]
        journey = self.journey.report()["journey_health"]
        return {
            "screenshot_coverage": coverage,
            "verified_screenshots": verified,
            "navigation_health": navigation,
            "consistency_score": consistency,
            "journey_health": journey,
        }

    def report(self) -> dict[str, Any]:
        m = self.metrics()
        gates = [
            {"gate": "screenshot_coverage", "value": m["screenshot_coverage"],
             "threshold": THRESHOLD, "passed": m["screenshot_coverage"] >= THRESHOLD},
            {"gate": "verified_screenshots", "value": m["verified_screenshots"],
             "threshold": THRESHOLD, "passed": m["verified_screenshots"] >= THRESHOLD},
            {"gate": "navigation_health", "value": m["navigation_health"],
             "threshold": THRESHOLD, "passed": m["navigation_health"] >= THRESHOLD},
            {"gate": "consistency_score", "value": m["consistency_score"],
             "threshold": THRESHOLD, "passed": m["consistency_score"] >= THRESHOLD},
        ]
        release_ready = all(g["passed"] for g in gates)
        return {
            "gates": gates,
            "release_ready": release_ready,
            "metrics": m,
        }
