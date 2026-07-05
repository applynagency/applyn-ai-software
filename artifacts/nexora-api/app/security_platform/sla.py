"""Security remediation SLA evaluation (Sprint 65E)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

DEFAULT_SLA_DAYS = {
    "CRITICAL": 1,
    "HIGH": 7,
    "MEDIUM": 30,
    "LOW": 90,
}

DEFAULT_WARNING_HOURS = 24


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def resolve_due_days(policies: list[dict], *, severity: str, environment: str | None) -> int:
    sev = severity.upper()
    env = (environment or "").lower()
    for pol in policies:
        if not pol.get("enabled", True):
            continue
        if pol.get("severity", "").upper() != sev:
            continue
        pol_env = (pol.get("environment") or "").lower()
        if pol_env and env and pol_env != env:
            continue
        return int(pol.get("due_days", DEFAULT_SLA_DAYS.get(sev, 30)))
    return DEFAULT_SLA_DAYS.get(sev, 30)


def compute_sla_due_at(
    *,
    created_at: datetime,
    severity: str,
    environment: str | None,
    policies: list[dict],
) -> datetime:
    days = resolve_due_days(policies, severity=severity, environment=environment)
    return created_at + timedelta(days=days)


def evaluate_sla(
    finding: dict,
    *,
    policies: list[dict],
    now: datetime | None = None,
) -> dict[str, Any]:
    now = _ensure_aware(now or datetime.now(UTC))
    created = finding.get("created_at") or now
    if isinstance(created, str):
        created = datetime.fromisoformat(created.replace("Z", "+00:00"))
    created = _ensure_aware(created)
    due_at = finding.get("sla_due_at")
    if due_at is None:
        due_at = compute_sla_due_at(
            created_at=created,
            severity=finding.get("severity", "MEDIUM"),
            environment=finding.get("environment"),
            policies=policies,
        )
    elif isinstance(due_at, str):
        due_at = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
    due_at = _ensure_aware(due_at)

    breached = now > due_at and finding.get("status") in ("OPEN", "ACKNOWLEDGED", "IN_REMEDIATION")
    warning_hours = DEFAULT_WARNING_HOURS
    for pol in policies:
        if pol.get("severity", "").upper() == (finding.get("severity") or "").upper():
            warning_hours = int(pol.get("warning_hours", warning_hours))
            break
    due_soon = (due_at - now) <= timedelta(hours=warning_hours) and not breached

    return {
        "sla_due_at": due_at,
        "sla_breached": breached,
        "due_soon": due_soon and not breached,
        "owner_team": finding.get("owner_team"),
    }


def sla_dashboard_counts(findings: list[dict], *, policies: list[dict], now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(UTC)
    due_soon = breached = accepted = 0
    for f in findings:
        ev = evaluate_sla(f, policies=policies, now=now)
        if f.get("status") == "ACCEPTED_RISK":
            accepted += 1
        if ev["sla_breached"]:
            breached += 1
        elif ev["due_soon"]:
            due_soon += 1
    return {"due_soon": due_soon, "breached": breached, "accepted_risk": accepted}
