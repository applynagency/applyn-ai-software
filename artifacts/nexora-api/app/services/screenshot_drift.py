"""Sprint 56C — ScreenshotDriftService.

Detects documentation drift by comparing documented screenshot/route/module
references against the UI registry, then summarises impact per affected module.
Read-only, deterministic.
"""

from __future__ import annotations

from typing import Any

from app.services.customer_success_content import JOURNEYS, MODULES
from app.services.documentation_verification import DocumentationVerificationService


def _impacted_guides(module_key: str) -> int:
    count = sum(1 for m in MODULES if m["key"] == module_key)
    count += sum(
        1 for j in JOURNEYS if any(s.get("module") == module_key for s in j["stages"])
    )
    return count


def _severity(broken: int, outdated: int) -> str:
    if broken > 0:
        return "CRITICAL" if broken >= 5 else "HIGH"
    if outdated >= 6:
        return "MEDIUM"
    return "LOW"


def _recommended_action(broken: int, outdated: int) -> str:
    if broken > 0:
        return "Fix documented route/module references or remove dead screenshots."
    return "Re-capture outdated screenshots against the current UI."


class ScreenshotDriftService:
    def __init__(self) -> None:
        self.verification = DocumentationVerificationService()

    def report(self) -> dict[str, Any]:
        records = self.verification.verifications()["items"]
        drifted = [r for r in records if r["verification_status"] in ("OUTDATED", "BROKEN")]
        by_module: dict[str, dict[str, int]] = {}
        for r in drifted:
            m = r["module"]
            slot = by_module.setdefault(m, {"OUTDATED": 0, "BROKEN": 0})
            slot[r["verification_status"]] += 1

        items = []
        sev_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
        for module, counts in sorted(by_module.items()):
            broken = counts["BROKEN"]
            outdated = counts["OUTDATED"]
            severity = _severity(broken, outdated)
            sev_counts[severity] += 1
            items.append({
                "affected_module": module,
                "screenshot_count": broken + outdated,
                "impacted_guides": _impacted_guides(module),
                "severity": severity,
                "recommended_action": _recommended_action(broken, outdated),
            })

        return {
            "items": items,
            "total_drift": len(items),
            "by_severity": sev_counts,
            "drift_detected": len(items) > 0,
        }
