"""Customer pilot deployment readiness evaluator (Sprint 67E)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.pilot.operations_readiness import evaluate_pilot_operations_readiness
from app.pilot.monitoring_rules import IN_APP_ONLY_NOTIFICATION_SCOPE

EXPECTED_MIGRATION_HEAD = "0039_customer_pilot_operations"

_INSECURE_JWT_MARKERS = frozenset({
    "your-super-secret-key-change-in-production",
    "changeme",
    "secret",
    "dev-secret",
})


def evaluate_pilot_deployment_readiness(payload: dict[str, Any]) -> dict[str, Any]:
    """Pure evaluator — GO / NO_GO / INSUFFICIENT_EVIDENCE for production-like deployment."""
    checks: list[dict] = []
    failed: list[str] = []
    insufficient: list[str] = []
    remediation: list[str] = []

    def _check(name: str, ok: bool, *, detail: str, fix: str | None = None, critical: bool = True) -> None:
        checks.append({"name": name, "passed": ok, "detail": detail, "fix": fix})
        if not ok:
            if critical:
                failed.append(name)
            else:
                insufficient.append(name)
            if fix:
                remediation.append(fix)

    _check(
        "api_version",
        bool(payload.get("app_version")),
        detail=f"API version {payload.get('app_version', 'unknown')}",
        fix="Deploy current Nexora API image",
        critical=False,
    )

    head = payload.get("migration_head")
    current = payload.get("migration_current")
    _check(
        "migration_at_head",
        current == head == EXPECTED_MIGRATION_HEAD,
        detail=f"DB revision {current or 'unknown'}; expected {EXPECTED_MIGRATION_HEAD}",
        fix="Run alembic upgrade head before customer onboarding",
    )

    _check(
        "single_alembic_head",
        int(payload.get("alembic_head_count", 0)) == 1,
        detail=f"Alembic heads: {payload.get('alembic_head_count', 0)}",
        fix="Resolve branched Alembic migrations to exactly one head",
    )

    ops = evaluate_pilot_operations_readiness(payload.get("operations_payload") or {})
    for oc in ops.get("checks", []):
        checks.append({
            "name": f"ops_{oc['name']}",
            "passed": oc["passed"],
            "detail": oc.get("detail", ""),
            "fix": oc.get("fix"),
        })
    for name in ops.get("failed_checks", []):
        failed.append(f"ops_{name}")
    for name in ops.get("insufficient_evidence", []):
        insufficient.append(f"ops_{name}")
    remediation.extend(ops.get("remediation_steps", []))

    _check(
        "pilot_mode_enabled",
        payload.get("pilot_mode_enabled") is True,
        detail="PILOT_MODE_ENABLED=true" if payload.get("pilot_mode_enabled") else "Pilot mode disabled",
        fix="Set PILOT_MODE_ENABLED=true for customer pilot",
    )

    _check(
        "pilot_org_allowlist",
        payload.get("pilot_mode_all_orgs") is False and bool(payload.get("pilot_organization_ids")),
        detail=(
            f"Allowlist enforced ({len(payload.get('pilot_organization_ids') or [])} orgs)"
            if payload.get("pilot_mode_all_orgs") is False
            else "PILOT_MODE_ALL_ORGS=true — not production-like"
        ),
        fix="Set PILOT_MODE_ALL_ORGS=false and populate PILOT_ORGANIZATION_IDS with internal tenant only",
        critical=payload.get("environment") in ("production", "staging"),
    )

    _check(
        "debug_disabled",
        not payload.get("debug_enabled"),
        detail="Debug off" if not payload.get("debug_enabled") else "DEBUG=true",
        fix="Disable DEBUG in production-like environments",
    )

    _check(
        "secure_secrets",
        not payload.get("insecure_jwt_secret"),
        detail="JWT secret not a known placeholder" if not payload.get("insecure_jwt_secret") else "Insecure JWT secret detected",
        fix="Rotate JWT_SECRET_KEY to a unique production value",
    )

    cors = payload.get("cors_origins") or []
    _check(
        "cors_not_wildcard",
        "*" not in cors,
        detail="No wildcard CORS" if "*" not in cors else "Wildcard CORS configured",
        fix="Set explicit CORS_ALLOWED_ORIGINS for authenticated portal",
    )

    _check(
        "rate_limiting_enabled",
        payload.get("rate_limit_enabled") is True,
        detail="Rate limiting enabled" if payload.get("rate_limit_enabled") else "Rate limiting disabled",
        fix="Enable RATE_LIMIT_ENABLED in production-like config",
        critical=payload.get("environment") in ("production", "staging"),
    )

    _check(
        "health_endpoints",
        payload.get("health_ok") is True,
        detail=payload.get("health_detail", "Health check status unknown"),
        fix="Resolve failing /readyz or /livez dependency checks",
    )

    _check(
        "metrics_enabled",
        payload.get("metrics_enabled") is True,
        detail="Metrics exposition enabled" if payload.get("metrics_enabled") else "METRICS_ENABLED=false",
        fix="Enable METRICS_ENABLED and configure Prometheus scrape",
        critical=False,
    )

    if payload.get("email_notifications_enabled"):
        if payload.get("smtp_configured"):
            if payload.get("smtp_delivery_verified"):
                _check("smtp_delivery", True, detail="SMTP delivery verified in internal test", critical=False)
            else:
                insufficient.append("smtp_delivery_unverified")
                _check(
                    "smtp_delivery",
                    False,
                    detail="SMTP configured but delivery not verified",
                    fix="Run internal SMTP delivery test before claiming email works",
                    critical=False,
                )
        else:
            insufficient.append("smtp_not_configured")
            _check(
                "smtp_delivery",
                False,
                detail="Email notifications enabled but SMTP_HOST is not configured",
                fix="Configure SMTP_HOST and verify internal delivery test",
                critical=False,
            )
    else:
        _check(
            "smtp_delivery",
            True,
            detail=IN_APP_ONLY_NOTIFICATION_SCOPE,
            fix="Set PILOT_EMAIL_NOTIFICATIONS_ENABLED=true only when email delivery is advertised",
            critical=False,
        )

    if payload.get("alert_receiver_configured"):
        if payload.get("alert_delivery_verified"):
            _check("alert_delivery", True, detail="Test alert delivered to internal channel", critical=False)
        else:
            insufficient.append("alert_delivery_unverified")
            _check(
                "alert_delivery",
                False,
                detail="Alert receiver configured but delivery not verified",
                fix="Fire a test alert and confirm receipt",
                critical=False,
            )
    else:
        insufficient.append("alert_receiver_not_configured")
        _check(
            "alert_delivery",
            False,
            detail="Alert delivery INSUFFICIENT_EVIDENCE — no receiver configured",
            fix="Configure internal alert receiver and run test alert",
            critical=False,
        )

    if payload.get("backup_manifest_valid") is True:
        _check("backup_integrity", True, detail="Latest backup manifest validated", critical=False)
    elif payload.get("backup_manifest_valid") is False:
        _check(
            "backup_integrity",
            False,
            detail="Backup integrity check failed",
            fix="Run pg_backup.sh and validate with pg_restore --list",
            critical=False,
        )
    else:
        insufficient.append("backup_not_validated")
        _check(
            "backup_integrity",
            False,
            detail="Backup not validated in this environment",
            fix="Run scripts/pilot_sprint67e_backup_validate.sh before onboarding",
            critical=False,
        )

    if payload.get("dry_run_completed"):
        _check(
            "internal_dry_run",
            payload.get("dry_run_passed") is True,
            detail=payload.get("dry_run_detail", "Internal dry run completed"),
            fix="Complete internal portal dry run per Sprint 67E runbook",
            critical=False,
        )
    else:
        insufficient.append("dry_run_pending")
        _check(
            "internal_dry_run",
            False,
            detail="Internal dry run not recorded",
            fix="Run scripts/pilot_sprint67e_deployment_readiness.py",
            critical=False,
        )

    # Deduplicate remediation while preserving order
    seen: set[str] = set()
    unique_remediation = []
    for step in remediation:
        if step not in seen:
            seen.add(step)
            unique_remediation.append(step)

    failed = list(dict.fromkeys(failed))
    insufficient = [x for x in dict.fromkeys(insufficient) if x not in failed]

    if failed:
        verdict = "NO_GO"
    elif insufficient:
        verdict = "INSUFFICIENT_EVIDENCE"
    else:
        verdict = "GO"

    return {
        "verdict": verdict,
        "checks": checks,
        "failed_checks": failed,
        "insufficient_evidence": insufficient,
        "remediation_steps": unique_remediation,
        "operations_verdict": ops.get("verdict"),
        "notification_scope": (
            "in_app_and_email" if payload.get("email_notifications_enabled") else "in_app_only"
        ),
        "notification_scope_detail": (
            None if payload.get("email_notifications_enabled") else IN_APP_ONLY_NOTIFICATION_SCOPE
        ),
        "evaluated_at": datetime.now(UTC).isoformat(),
        "read_only": True,
        "environment": payload.get("environment"),
    }
