"""Remediation execution binding for Security Platform (Sprint 65E)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

HIGH_RISK_KINDS = {
    "REVOKE_API_KEY", "DISABLE_SERVICE_ACCOUNT", "ROTATE_CREDENTIAL",
    "APPLY_TERRAFORM", "NETWORK_POLICY", "IMAGE_REBUILD", "REDEPLOY",
}

LOW_RISK_AUTO_KINDS = {"CREATE_TICKET", "NOTIFY_OWNER"}


def requires_human_approval(kind: str, *, org_policy: dict | None = None) -> bool:
    k = kind.upper()
    if k in HIGH_RISK_KINDS:
        return True
    if k in LOW_RISK_AUTO_KINDS:
        allowed = (org_policy or {}).get("auto_execute_low_risk", False)
        return not allowed
    return True


def build_execution_plan(proposal: dict, finding: dict) -> dict[str, Any]:
    kind = proposal.get("kind", "").upper()
    return {
        "action": kind,
        "finding_id": finding.get("id"),
        "target": finding.get("resource"),
        "rollback_plan": proposal.get("rollback_plan"),
        "checkpoints": ["validated", "executing", "verifying"],
        "task_name": "security_remediation_execute",
    }


def apply_execution_result(
    *,
    success: bool,
    verification: dict | None = None,
) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    if success:
        return {
            "execution_status": "COMPLETED",
            "finding_status": "RESOLVED" if (verification or {}).get("verified") else "IN_REMEDIATION",
            "verification": verification or {"verified": False, "at": now},
        }
    return {
        "execution_status": "FAILED",
        "finding_status": None,
        "verification": {"verified": False, "at": now, "error": "execution_failed"},
    }
