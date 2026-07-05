"""Customer pilot operations readiness evaluator (Sprint 67D)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def evaluate_pilot_operations_readiness(payload: dict[str, Any]) -> dict[str, Any]:
    """Pure evaluator — GO / NO_GO / INSUFFICIENT_EVIDENCE."""
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

    redis_ok = payload.get("redis_available", False)
    _check(
        "redis_connectivity",
        redis_ok,
        detail="Redis reachable" if redis_ok else "Redis unavailable",
        fix="Restore Redis connectivity before relying on reminder delivery",
    )

    worker_ok = payload.get("worker_recent", False)
    _check(
        "arq_worker_heartbeat",
        worker_ok,
        detail=payload.get("worker_detail", "Worker status unknown"),
        fix="Ensure Arq worker is running and processing cron jobs",
        critical=bool(payload.get("job_queue_enabled")),
    )

    cron_registered = payload.get("reminder_cron_registered", False)
    _check(
        "approval_reminder_cron_registered",
        cron_registered,
        detail="Reminder cron registered" if cron_registered else "Reminder cron not registered",
        fix="Enable PILOT_MODE_ENABLED and JOB_CRON_ENABLED with worker on default queue",
    )

    lock_ok = payload.get("scheduler_lock_available", False)
    _check(
        "scheduler_lock_capability",
        lock_ok or not payload.get("distributed_lock_enabled"),
        detail=payload.get("scheduler_lock_detail", "Scheduler lock check"),
        fix="Verify Redis lock configuration or disable DISTRIBUTED_LOCK_ENABLED for single-node",
        critical=payload.get("distributed_lock_enabled", False),
    )

    last_success = payload.get("reminder_last_success_at")
    stale_hours = payload.get("reminder_stale_hours", 24)
    if last_success:
        ts = datetime.fromisoformat(last_success) if isinstance(last_success, str) else last_success
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        age_h = (datetime.now(UTC) - ts).total_seconds() / 3600
        _check(
            "reminder_last_success",
            age_h <= stale_hours,
            detail=f"Last successful reminder run {age_h:.1f}h ago",
            fix="Investigate cron_customer_pilot_approval_reminders failures in worker logs",
        )
    else:
        insufficient.append("reminder_never_ran")
        _check(
            "reminder_last_success",
            False,
            detail="No successful reminder cron run recorded yet",
            fix="Wait for first cron cycle or run reminder job manually in staging",
            critical=False,
        )

    consec = int(payload.get("reminder_consecutive_failures", 0))
    _check(
        "reminder_failure_streak",
        consec < 3,
        detail=f"Consecutive reminder failures: {consec}",
        fix="Review worker logs and Redis connectivity; resolve root cause before customer onboarding",
    )

    oldest_q = payload.get("notification_queue_oldest_seconds")
    if oldest_q is not None:
        _check(
            "notification_queue_age",
            float(oldest_q) < 3600,
            detail=f"Oldest queued delivery age: {int(oldest_q)}s",
            fix="Process or requeue failed notification deliveries",
            critical=False,
        )

    failed_deliveries = int(payload.get("failed_delivery_count", 0))
    _check(
        "failed_delivery_backlog",
        failed_deliveries < 50,
        detail=f"Failed notification deliveries: {failed_deliveries}",
        fix="Use delivery requeue endpoint for failed records after fixing root cause",
        critical=False,
    )

    _check("clock_sanity", payload.get("clock_sane", True), detail="System clock uses UTC", fix="Sync NTP on worker nodes")

    email_state = payload.get("email_configured")
    _check(
        "email_provider",
        True,
        detail="Email configured" if email_state else "Email not configured (in-app only)",
        fix="Configure SMTP_HOST for email reminders if required",
        critical=False,
    )

    if insufficient and not failed:
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
        "evaluated_at": datetime.now(UTC).isoformat(),
        "read_only": True,
    }


def customer_safe_operations_status(ops: dict[str, Any]) -> dict[str, str]:
    """Customer-safe operational labels — no infrastructure names."""
    verdict = ops.get("verdict", "INSUFFICIENT_EVIDENCE")
    checks = {c["name"]: c["passed"] for c in ops.get("checks", [])}

    def _label(name: str) -> str:
        if checks.get(name) is True:
            return "operational"
        if checks.get(name) is False:
            return "degraded"
        return "unknown"

    return {
        "notifications_operational": _label("redis_connectivity") if verdict != "NO_GO" else "degraded",
        "approval_reminders_operational": _label("reminder_last_success"),
        "support_monitoring_operational": "operational" if verdict == "GO" else "degraded",
        "overall_verdict": verdict,
        "degradation_notice": (
            "Reminder delivery may be delayed. Your approval status and timeline remain authoritative."
            if verdict != "GO" else None
        ),
    }
