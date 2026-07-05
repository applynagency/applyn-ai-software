"""Rollback policy and recommendations (Sprint 65F)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

HIGH_RISK_ENVIRONMENTS = frozenset({"PRODUCTION"})


def recommend_rollback(
    *,
    health_gate_decision: str,
    environment_tier: str,
    auto_rollback_policy: bool = False,
    provider_supports_auto: bool = False,
) -> dict[str, Any]:
    should = health_gate_decision in ("FAIL", "INSUFFICIENT_EVIDENCE")
    automatic = (
        auto_rollback_policy
        and provider_supports_auto
        and environment_tier in HIGH_RISK_ENVIRONMENTS
        and health_gate_decision == "FAIL"
    )
    if automatic:
        kind = "AUTOMATIC"
        status = "PENDING_APPROVAL"
    elif should:
        kind = "RECOMMENDED"
        status = "RECOMMENDED"
    else:
        kind = "NONE"
        status = "NOT_NEEDED"
    return {
        "kind": kind,
        "status": status,
        "automatic": automatic,
        "requires_approval": environment_tier in HIGH_RISK_ENVIRONMENTS or not automatic,
        "reason": f"health_gate={health_gate_decision}",
        "recommended_at": datetime.now(UTC).isoformat(),
        "create_incident": health_gate_decision == "FAIL" and environment_tier == "PRODUCTION",
    }


def apply_rollback_result(*, success: bool, target_revision: str | None = None) -> dict[str, Any]:
    return {
        "status": "SUCCEEDED" if success else "FAILED",
        "target_revision": target_revision,
        "verified": success,
        "completed_at": datetime.now(UTC).isoformat(),
    }
