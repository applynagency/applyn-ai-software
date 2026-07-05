"""Read-only customer pilot launch readiness evaluator (Sprint 66K)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

K8S_MIN_RBAC = (
    "deployments:get,list,watch",
    "deployments/scale:get,patch,update",
    "pods:get,list,watch",
    "events:get,list,watch",
)

REQUIRED_INTEGRATIONS = ("KUBERNETES", "GITHUB", "PROMETHEUS")

_PROVIDER_ALIASES: dict[str, frozenset[str]] = {
    "GITHUB": frozenset({"GITHUB", "GITHUB_ENTERPRISE", "GITEA"}),
    "KUBERNETES": frozenset({"KUBERNETES"}),
    "PROMETHEUS": frozenset({"PROMETHEUS"}),
}


def _integrations_for_provider(integrations: list[dict], provider: str) -> list[dict]:
    allowed = _PROVIDER_ALIASES.get(provider, frozenset({provider}))
    return [i for i in integrations if (i.get("provider_type") or "").upper() in allowed]

K8S_WRITE_CAPS = frozenset({
    "kubernetes.workloads.write",
    "kubernetes.workloads.scale",
    "write",
})


def evaluate_customer_launch_readiness(payload: dict[str, Any]) -> dict[str, Any]:
    """Pure evaluator — no side effects. Returns GO, NO_GO, or INSUFFICIENT_EVIDENCE."""
    checks: list[dict[str, Any]] = []
    failed: list[str] = []
    insufficient: list[str] = []
    remediation: list[str] = []

    def _check(name: str, ok: bool, *, detail: str, fix: str | None = None, evidence: dict | None = None) -> None:
        checks.append({
            "name": name,
            "passed": ok,
            "detail": detail,
            "evidence_ref": evidence or {},
        })
        if not ok:
            failed.append(name)
            if fix:
                remediation.append(fix)

    if not payload.get("pilot_mode_enabled"):
        _check(
            "pilot_feature_gating",
            False,
            detail="Pilot mode is not enabled for this deployment",
            fix="Enable PILOT_MODE_ENABLED and organization allowlist",
        )
    else:
        _check("pilot_feature_gating", True, detail="Pilot mode enabled")

    if not payload.get("org_allowlisted"):
        _check(
            "organization_allowlist",
            False,
            detail="Organization is not on the pilot allowlist",
            fix="Add organization to PILOT_ORGANIZATION_IDS or enable PILOT_MODE_ALL_ORGS",
        )
    else:
        _check("organization_allowlist", True, detail="Organization is pilot-eligible")

    enrollment = payload.get("enrollment") or {}
    if not enrollment.get("id"):
        insufficient.append("enrollment_missing")
        _check("enrollment_present", False, detail="No pilot enrollment found", fix="Start an onboarding path")
    else:
        _check("enrollment_present", True, detail="Pilot enrollment exists", evidence={"enrollment_id": enrollment.get("id")})

    if enrollment.get("kill_switch"):
        _check(
            "kill_switch_inactive",
            False,
            detail="Pilot kill switch is active",
            fix="Disable kill switch before customer pilot",
        )
    else:
        _check("kill_switch_inactive", True, detail="Kill switch is not active")

    op_limit = enrollment.get("operation_limit")
    if op_limit is not None and int(op_limit) < 1:
        _check("operation_limit", False, detail="Operation limit must be at least 1", fix="Set operation_limit >= 1")
    else:
        _check(
            "operation_limit",
            True,
            detail=f"Operation limit configured ({op_limit})",
            evidence={"operation_limit": op_limit},
        )

    integrations = payload.get("integrations") or []
    for provider in REQUIRED_INTEGRATIONS:
        matches = _integrations_for_provider(integrations, provider)
        if not matches:
            insufficient.append(f"integration_{provider.lower()}_missing")
            _check(
                f"integration_{provider.lower()}",
                False,
                detail=f"No {provider} integration registered",
                fix=f"Connect and validate {provider} integration",
            )
            continue
        conn = matches[0]
        state = (conn.get("lifecycle_state") or "").upper()
        mode = (conn.get("provider_mode") or "").lower()
        fresh = conn.get("freshness_ok", False)
        ok = state == "CONNECTED" and mode == "live" and fresh
        _check(
            f"integration_{provider.lower()}",
            ok,
            detail=f"{provider} state={state} mode={mode} fresh={fresh}",
            fix=f"Validate {provider} integration and ensure live CONNECTED state",
            evidence={
                "connection_id": conn.get("id"),
                "lifecycle_state": state,
                "provider_mode": mode,
            },
        )
        if provider == "KUBERNETES":
            caps = set((conn.get("capabilities") or {}).keys())
            has_write = bool(caps & K8S_WRITE_CAPS)
            _check(
                "kubernetes_write_capability",
                has_write,
                detail="Namespace-scoped workload write capability required for pilot scale",
                fix="Grant deployments/scale patch within pilot namespace only",
                evidence={"capabilities": sorted(caps)[:12]},
            )
            rbac = conn.get("rbac_evidence") or {}
            if rbac:
                _check(
                    "kubernetes_rbac_evidence",
                    rbac.get("namespace_scoped", False),
                    detail=rbac.get("summary", "RBAC evidence collected"),
                    fix="Limit ServiceAccount to single non-production namespace",
                    evidence=rbac,
                )
            else:
                insufficient.append("kubernetes_rbac_evidence_missing")
                _check(
                    "kubernetes_rbac_evidence",
                    False,
                    detail="RBAC evidence not yet collected",
                    fix="Run integration validation to capture RBAC evidence",
                )

    envs = payload.get("environments") or []
    non_prod = [e for e in envs if (e.get("tier") or "").upper() != "PRODUCTION"]
    prod = [e for e in envs if (e.get("tier") or "").upper() == "PRODUCTION"]
    _check(
        "non_production_environment",
        bool(non_prod),
        detail=f"{len(non_prod)} non-production environment(s) declared",
        fix="Declare at least one STAGING or DEVELOPMENT environment",
    )
    if prod:
        _check(
            "no_production_target",
            False,
            detail="Production environments must not be used in customer pilot",
            fix="Remove or exclude production tier from pilot scope",
        )
    else:
        _check("no_production_target", True, detail="No production environment in scope")

    contacts = payload.get("contacts") or {}
    has_approver = bool(contacts.get("approval_contact") or contacts.get("approver_email"))
    has_support = bool(contacts.get("support_contact"))
    _check(
        "approval_contact",
        has_approver,
        detail="Named approval contact configured" if has_approver else "Approval contact missing",
        fix="Configure approval contact in pilot enrollment",
    )
    _check(
        "support_contact",
        has_support,
        detail="Support contact configured" if has_support else "Support contact missing",
        fix="Configure support contact for pilot notifications",
    )

    if payload.get("backup_restore_documented") is False:
        insufficient.append("backup_restore_unverified")
        _check(
            "backup_restore_readiness",
            False,
            detail="Backup/restore readiness not documented",
            fix="Document rollback and restore procedure for pilot namespace",
        )
    else:
        _check("backup_restore_readiness", True, detail="Backup/restore readiness acknowledged")

    if insufficient:
        verdict = "INSUFFICIENT_EVIDENCE"
    elif failed:
        verdict = "NO_GO"
    else:
        verdict = "GO"

    return {
        "verdict": verdict,
        "checks": checks,
        "failed_checks": failed,
        "insufficient_evidence": insufficient,
        "remediation_steps": remediation,
        "minimum_rbac": list(K8S_MIN_RBAC),
        "evaluated_at": datetime.now(UTC).isoformat(),
        "read_only": True,
    }


def integration_freshness_ok(last_validated_at: datetime | None, *, max_age_hours: int = 24) -> bool:
    if last_validated_at is None:
        return False
    ts = last_validated_at if last_validated_at.tzinfo else last_validated_at.replace(tzinfo=UTC)
    return datetime.now(UTC) - ts <= timedelta(hours=max_age_hours)
