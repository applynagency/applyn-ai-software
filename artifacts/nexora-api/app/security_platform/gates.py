"""Security policy gates for Delivery and IaC workflows (Sprint 65E)."""

from __future__ import annotations

from typing import Any


def evaluate_gate(
    findings: list[dict],
    *,
    policy_mode: str = "WARN",
    scope: dict | None = None,
) -> dict[str, Any]:
    """Return gate decision from canonical findings. Never includes secrets."""
    scope = scope or {}
    open_findings = [
        f for f in findings
        if f.get("status") in ("OPEN", "ACKNOWLEDGED", "IN_REMEDIATION")
    ]
    if scope.get("repository"):
        open_findings = [f for f in open_findings if scope["repository"] in (f.get("resource") or "")]
    if scope.get("environment"):
        open_findings = [f for f in open_findings if (f.get("environment") or "").lower() == scope["environment"].lower()]

    critical = [f for f in open_findings if f.get("severity") == "CRITICAL"]
    high = [f for f in open_findings if f.get("severity") == "HIGH"]
    mode = (policy_mode or "WARN").upper()

    if critical:
        decision = "BLOCK" if mode in ("BLOCK", "APPROVAL_REQUIRED") else "WARN"
        if mode == "APPROVAL_REQUIRED":
            decision = "APPROVAL_REQUIRED"
    elif high and mode == "BLOCK":
        decision = "BLOCK"
    elif high:
        decision = "WARN" if mode == "WARN" else "APPROVAL_REQUIRED"
    else:
        decision = "PASS"

    summary = [
        {
            "id": f.get("id"),
            "title": f.get("title"),
            "severity": f.get("severity"),
            "source": f.get("source"),
            "remediation_link": f"/security-platform/remediation?finding={f.get('id')}",
        }
        for f in (critical + high)[:10]
    ]
    return {
        "decision": decision,
        "critical_count": len(critical),
        "high_count": len(high),
        "finding_summary": summary,
        "blocked": decision in ("BLOCK", "APPROVAL_REQUIRED"),
    }
