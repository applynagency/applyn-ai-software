"""Sprint 56A — DocumentationQualityService.

Scores documentation maturity per customer-facing module across eight dimensions:

    overview, navigation, prerequisites, steps, screenshots, examples,
    troubleshooting, faq

coverage_score is 0-100. Quality levels:

    0-59   Poor
    60-79  Good
    80-94  Excellent
    95-100 Production Ready

Target: all customer-facing modules >= 95 (Production Ready).
"""

from __future__ import annotations

from typing import Any

from app.services.customer_success_content import MODULES, get_module

DIMENSIONS = [
    "overview",
    "navigation",
    "prerequisites",
    "steps",
    "examples",
    "screenshots",
    "troubleshooting",
    "faq",
    "architecture_diagram",
    "expected_results",
]
_WEIGHT = 100 / len(DIMENSIONS)

MIN_STEPS = 5
MIN_FAQ = 5
MIN_TROUBLESHOOTING = 3
MIN_SCREENSHOTS = 3
_OVERVIEW_KEYS = ("what", "why", "business_value", "who", "when")
_EXAMPLE_KEYS = ("scenario", "walkthrough", "outcome")


def _level(score: int) -> str:
    if score >= 95:
        return "Production Ready"
    if score >= 80:
        return "Excellent"
    if score >= 60:
        return "Good"
    return "Poor"


class DocumentationQualityService:
    """Computes documentation coverage scores for modules and an overall report."""

    def _dimension_flags(self, module: dict[str, Any]) -> dict[str, bool]:
        overview = module.get("overview") or {}
        navigation = module.get("navigation") or {}
        steps = module.get("steps") or []
        example = module.get("example") or {}
        return {
            "overview": all(str(overview.get(k, "")).strip() for k in _OVERVIEW_KEYS),
            "navigation": bool(navigation.get("path")) and bool(navigation.get("route")),
            "prerequisites": len(module.get("prerequisites") or []) >= 1,
            "steps": len(steps) >= MIN_STEPS
            and all(s.get("action") and s.get("expected") and s.get("screenshot") for s in steps),
            "examples": all(str(example.get(k, "")).strip() for k in _EXAMPLE_KEYS),
            "screenshots": len(module.get("screenshots") or []) >= MIN_SCREENSHOTS,
            "troubleshooting": len(module.get("troubleshooting") or []) >= MIN_TROUBLESHOOTING,
            "faq": len(module.get("faq") or []) >= MIN_FAQ,
            # Sprint 56A.1 — Architecture Diagram + Expected Results / Screens.
            "architecture_diagram": bool(str(module.get("architecture_diagram", "")).strip()),
            "expected_results": bool(steps)
            and all(s.get("expected") and s.get("expected_screens") for s in steps),
        }

    def score_module(self, key: str) -> dict[str, Any] | None:
        module = get_module(key)
        if not module:
            return None
        flags = self._dimension_flags(module)
        score = round(sum(_WEIGHT for satisfied in flags.values() if satisfied))
        missing = [d for d, ok in flags.items() if not ok]
        return {
            "key": module["key"],
            "name": module["name"],
            "category": module["category"],
            "coverage_score": score,
            "level": _level(score),
            "dimensions": flags,
            "missing_dimensions": missing,
            "production_ready": score >= 95,
        }

    def report(self) -> dict[str, Any]:
        modules = [self.score_module(m["key"]) for m in MODULES]
        modules = [m for m in modules if m]
        total = len(modules)
        scores = [m["coverage_score"] for m in modules]
        average = round(sum(scores) / total) if total else 0
        production_ready = [m for m in modules if m["production_ready"]]
        return {
            "dimensions": DIMENSIONS,
            "target": 95,
            "modules_total": total,
            "average_score": average,
            "production_ready_count": len(production_ready),
            "passes_target": total > 0 and len(production_ready) == total,
            "level": _level(average),
            "modules": modules,
        }
