"""Release reliability analytics (Sprint 65F)."""

from __future__ import annotations

from typing import Any


def compute_release_analytics(
    *,
    reliabilities: list[dict],
    rollbacks: list[dict],
    promotions: list[dict],
    verifications: list[dict],
) -> dict[str, Any]:
    total = len(reliabilities)
    failed_verify = sum(1 for v in verifications if v.get("decision") in ("FAIL", "INSUFFICIENT_EVIDENCE"))
    succeeded = sum(1 for r in reliabilities if r.get("verification_status") == "PASSED")
    change_failures = sum(1 for r in rollbacks if r.get("status") in ("SUCCEEDED", "RECOMMENDED"))
    cfr = (change_failures / total) if total else 0.0
    return {
        "total_releases": total,
        "verification_passed": succeeded,
        "verification_failed": failed_verify,
        "rollbacks": len(rollbacks),
        "promotions_pending": sum(1 for p in promotions if p.get("status") == "PENDING"),
        "promotions_blocked": sum(1 for p in promotions if p.get("status") == "BLOCKED"),
        "change_failure_rate": round(cfr, 4),
        "simulated_rollouts": sum(1 for r in reliabilities if r.get("provider_mode") != "live"),
    }
