"""Pilot customer approval package builders (Sprint 66G)."""

from __future__ import annotations

import html
import json
from datetime import UTC, datetime
from typing import Any

BANNER = "PROPOSED ONLY — NOT APPROVED — NOT EXECUTED"


def build_approval_package(
    *,
    operation: dict[str, Any],
    approval: dict[str, Any],
    enrollment: dict[str, Any],
    baseline: dict[str, Any] | None,
    integration: dict[str, Any] | None,
    preflight: dict[str, Any] | None,
    organization_name: str = "Nexora Pilot Test",
    maintenance_window: str | None = None,
    evidence_limitations: list[str] | None = None,
    verification_plan: list[str] | None = None,
    integration_readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a redacted approval package suitable for JSON/Markdown/HTML export."""
    params = operation.get("params") or {}
    return {
        "banner": BANNER,
        "generated_at": datetime.now(UTC).isoformat(),
        "organization": {
            "id": operation.get("organization_id"),
            "name": organization_name,
        },
        "proposal": {
            "operation_id": operation.get("id"),
            "action": operation.get("action"),
            "template_id": operation.get("template_id"),
            "status": operation.get("status"),
            "execution_label": (preflight or {}).get("execution_label", "LIVE-ELIGIBLE / NOT EXECUTED"),
            "idempotency_key": operation.get("correlation_id"),
            "payload_hash": operation.get("payload_hash"),
        },
        "approval": {
            "approval_id": approval.get("id"),
            "status": approval.get("status"),
            "expires_at": approval.get("expires_at"),
            "approver_name": approval.get("approver_name"),
            "approver_email": approval.get("approver_email"),
            "payload_hash": approval.get("payload_hash"),
        },
        "target": {
            "integration_id": operation.get("cluster_id"),
            "namespace": params.get("namespace", "nexora-pilot"),
            "deployment": operation.get("resource_name"),
            "environment": approval.get("target_environment"),
            "environment_tier": "non-production",
        },
        "change": {
            "summary": approval.get("operation_summary"),
            "desired": params,
            "rollback_plan": approval.get("rollback_plan") or operation.get("rollback_plan"),
            "risk": params.get("risk_classification", "low"),
            "risk_explanation": params.get("risk_explanation"),
        },
        "before_state": operation.get("before_state"),
        "baseline_hash": (baseline or {}).get("hash") or (baseline or {}).get("current", {}).get("hash"),
        "verification_criteria": params.get("verification_criteria", []),
        "verification_plan": verification_plan or params.get("verification_criteria", []),
        "failure_criteria": params.get("failure_criteria", []),
        "rollback_trigger": params.get("rollback_trigger"),
        "maintenance_window": maintenance_window,
        "evidence_limitations": evidence_limitations or [],
        "integration_readiness": integration_readiness or integration,
        "preflight": preflight,
        "safety_statements": [
            "Approval alone does not execute any infrastructure mutation.",
            "A separate typed confirmation and execution step is required after approval.",
            "This package documents a proposed reversible scale operation only.",
        ],
        "enrollment": {
            "id": enrollment.get("id"),
            "kill_switch": enrollment.get("kill_switch", False),
            "operation_count": enrollment.get("operation_count", 0),
            "operation_limit": enrollment.get("operation_limit", 0),
        },
    }


def approval_package_markdown(package: dict[str, Any]) -> str:
    p = package
    lines = [
        f"# Pilot Approval Package",
        "",
        f"**{p['banner']}**",
        "",
        f"Generated: {p['generated_at']}",
        "",
        "## Proposal",
        f"- Operation ID: `{p['proposal']['operation_id']}`",
        f"- Action: `{p['proposal']['action']}`",
        f"- Status: `{p['proposal']['status']}`",
        f"- Execution label: `{p['proposal']['execution_label']}`",
        f"- Idempotency key: `{p['proposal']['idempotency_key']}`",
        f"- Payload hash: `{p['proposal']['payload_hash']}`",
        "",
        "## Pending approval",
        f"- Approval ID: `{p['approval']['approval_id']}`",
        f"- Status: `{p['approval']['status']}`",
        f"- Expires: {p['approval']['expires_at']}",
        f"- Approver: {p['approval']['approver_name']} <{p['approval']['approver_email']}>",
        "",
        "## Target",
        f"- Deployment: `{p['target']['deployment']}` in `{p['target']['namespace']}`",
        f"- Environment: {p['target']['environment']} ({p['target']['environment_tier']})",
        f"- Integration: `{p['target']['integration_id']}`",
        "",
        "## Change",
        p["change"]["summary"],
        "",
        f"**Rollback:** {p['change']['rollback_plan']}",
        "",
        f"**Baseline hash:** `{p.get('baseline_hash')}`",
        "",
    ]
    if p.get("maintenance_window"):
        lines.extend(["## Maintenance window", p["maintenance_window"], ""])
    lines.append("## Verification plan")
    for item in p.get("verification_plan") or p.get("verification_criteria") or []:
        lines.append(f"- {item}")
    if p.get("evidence_limitations"):
        lines.extend(["", "## Evidence limitations"])
        for item in p["evidence_limitations"]:
            lines.append(f"- {item}")
    lines.extend(["", "## Verification criteria"])
    for item in p.get("verification_criteria") or []:
        if item not in (p.get("verification_plan") or []):
            lines.append(f"- {item}")
    lines.extend(["", "## Safety statements"])
    for stmt in p.get("safety_statements") or []:
        lines.append(f"- {stmt}")
    return "\n".join(lines)


def approval_package_html(package: dict[str, Any]) -> str:
    md = approval_package_markdown(package)
    body = "<br>".join(html.escape(line) for line in md.splitlines())
    return (
        f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>Pilot Approval Package</title></head><body>"
        f"<h1 style='color:#b45309'>{html.escape(BANNER)}</h1>"
        f"<pre>{body}</pre></body></html>"
    )


def change_summary_markdown(package: dict[str, Any]) -> str:
    t = package["target"]
    c = package["change"]
    return "\n".join([
        "# Customer-Facing Change Summary",
        "",
        f"**{BANNER}**",
        "",
        f"Nexora proposes a controlled, reversible scale of deployment `{t['deployment']}` "
        f"in namespace `{t['namespace']}` ({t['environment_tier']}).",
        "",
        c["summary"],
        "",
        f"Rollback: {c['rollback_plan']}",
    ])


def execution_runbook_markdown(package: dict[str, Any]) -> str:
    t = package["target"]
    p = package["proposal"]
    return "\n".join([
        "# Operator Execution Runbook (future step — not executed in Sprint 66G)",
        "",
        f"**{BANNER}**",
        "",
        "Prerequisites:",
        "- Customer approval status is APPROVED and not expired",
        "- Payload hash matches proposal",
        "- Kill switch is false; operation limit and cooldown satisfied",
        "- Integration validation is fresh (CONNECTED + live)",
        "",
        "Steps (later sprint only):",
        f"1. Confirm operation `{p['operation_id']}` with typed resource name `{t['deployment']}`",
        "2. LiveMutationGate preflight runs with approval_satisfied=true",
        "3. Kubernetes scale patch applied via pilot integration",
        "4. Post-operation verification against criteria",
        f"5. Idempotency key: `{p['idempotency_key']}`",
    ])


def rollback_runbook_markdown(package: dict[str, Any]) -> str:
    c = package["change"]
    return "\n".join([
        "# Rollback Runbook",
        "",
        f"**{BANNER}**",
        "",
        f"Trigger: {package.get('rollback_trigger') or 'Any verification failure or insufficient evidence'}",
        "",
        f"Action: {c['rollback_plan']}",
        "",
        "Re-verify deployment available replicas and pod readiness after rollback.",
    ])


def verification_checklist_markdown(package: dict[str, Any]) -> str:
    lines = ["# Verification Checklist", "", f"**{BANNER}**", ""]
    for item in package.get("verification_criteria") or []:
        lines.append(f"- [ ] {item}")
    for item in package.get("failure_criteria") or []:
        lines.append(f"- [ ] Failure watch: {item}")
    return "\n".join(lines)


def decision_log_markdown(package: dict[str, Any]) -> str:
    return "\n".join([
        "# Decision Log — Sprint 66G Proposal Safety",
        "",
        f"**{BANNER}**",
        "",
        "Why this operation is safe to propose:",
        "- Single non-production deployment in isolated internal pilot namespace",
        "- Reversible scale 1→2 with explicit rollback 2→1",
        "- Namespace-scoped RBAC grants scale patch only; no delete/create/secrets/cluster access",
        "- LiveMutationGate preflight verified integration readiness; only approval blocks execution",
        "",
        "Intentionally not permitted in this sprint:",
        "- Granting approval or typed confirmation",
        "- Calling execution/confirm endpoints",
        "- Any Kubernetes mutation",
        "- Advancing CUSTOMER_APPROVAL, EXECUTE, VERIFY, or COMPLETE stages",
    ])
