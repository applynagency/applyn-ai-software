"""Staging go-live evidence collection helpers (Sprint 67F)."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.integration_readiness.evidence import redact_text
from app.pilot.customer_portal import assert_export_safe, sanitize_customer_view

EXPECTED_HEAD = "0039_customer_pilot_operations"

_SECRET_PATTERNS = (
    re.compile(r"(?i)(token|password|secret|api[_-]?key)\s*[:=]\s*\S+"),
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"-----BEGIN"),
    re.compile(r"postgresql://\S+"),
    re.compile(r"sk-ant-", re.I),
    re.compile(r"sk-[a-zA-Z0-9]{10,}", re.I),
)


def redact_evidence_blob(text: str) -> str:
    out = redact_text(text)
    for pat in _SECRET_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out


def safe_evidence_dict(data: Any) -> Any:
    return sanitize_customer_view(json.loads(redact_evidence_blob(json.dumps(data, default=str))))


def _contains_sensitive_keys(data: Any) -> bool:
    blocked = frozenset({
        "password", "secret", "token", "api_key", "jwt_secret_key", "confirmation_token",
    })
    if isinstance(data, dict):
        return any(
            k.lower() in blocked or _contains_sensitive_keys(v)
            for k, v in data.items()
        )
    if isinstance(data, list):
        return any(_contains_sensitive_keys(v) for v in data)
    return False


def write_evidence_file(path: Path, payload: dict) -> dict:
    """Write redacted JSON; fail closed if secrets detected."""
    if _contains_sensitive_keys(payload):
        return {"written": False, "path": str(path), "error": "sensitive keys detected"}
    safe = safe_evidence_dict(payload)
    try:
        assert_export_safe(safe)
    except Exception as exc:
        return {"written": False, "path": str(path), "error": str(exc)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe, indent=2), encoding="utf-8")
    return {"written": True, "path": str(path)}


def compute_go_live_decision(evidence: dict[str, Any]) -> dict[str, Any]:
    """Derive final GO / NO_GO / INSUFFICIENT_EVIDENCE from collected evidence."""
    blockers: list[str] = []
    insufficient: list[str] = []
    passed: list[str] = []

    cfg = evidence.get("configuration_validation") or {}
    if cfg.get("debug_enabled"):
        blockers.append("DEBUG must be false for staging go-live")
    if cfg.get("pilot_mode_all_orgs"):
        blockers.append("PILOT_MODE_ALL_ORGS must be false")
    if not cfg.get("pilot_mode_enabled"):
        blockers.append("PILOT_MODE_ENABLED must be true")

    mig = evidence.get("migration_state") or {}
    if mig.get("current") != EXPECTED_HEAD or mig.get("head") != EXPECTED_HEAD:
        blockers.append(f"Migration must be at {EXPECTED_HEAD}")
    if mig.get("head_count") != 1:
        blockers.append("Exactly one Alembic head required")

    ops = evidence.get("operations_readiness") or {}
    if ops.get("verdict") != "GO":
        blockers.append(f"operations_readiness={ops.get('verdict')}")

    dep = evidence.get("deployment_readiness") or {}
    if dep.get("verdict") not in ("GO",):
        if dep.get("verdict") == "INSUFFICIENT_EVIDENCE":
            insufficient.append("deployment_readiness_insufficient_evidence")
        else:
            blockers.append(f"deployment_readiness={dep.get('verdict')}")

    sched = evidence.get("scheduler_reminder_validation") or {}
    if not sched.get("scheduler_lock_acquired"):
        blockers.append("scheduler lock not acquired in validation run")
    if not sched.get("duplicate_prevented", True):
        blockers.append("reminder idempotency failed")

    smtp = evidence.get("smtp_validation") or {}
    if smtp.get("status") == "CONFIGURED_NOT_VERIFIED":
        insufficient.append("smtp_configured_but_not_verified")
    elif smtp.get("status") == "NOT_CONFIGURED":
        passed.append("smtp_not_configured_in_app_only_scope")

    prom = evidence.get("prometheus_scrape_validation") or {}
    if not prom.get("metrics_present"):
        insufficient.append("prometheus_metrics_not_observed_on_api")

    alert = evidence.get("alert_delivery_validation") or {}
    if alert.get("status") != "DELIVERED":
        insufficient.append("alert_delivery_not_proven")

    backup = evidence.get("backup_restore_validation") or {}
    if not backup.get("valid"):
        blockers.append("backup_restore_validation_failed")
    elif backup.get("isolated_restore") == "INSUFFICIENT_EVIDENCE":
        insufficient.append("isolated_restore_not_proven")

    portal = evidence.get("portal_dry_run") or {}
    if not portal.get("passed"):
        insufficient.append("portal_dry_run_incomplete")

    runbook = evidence.get("runbook_walkthrough") or {}
    if not runbook.get("completed"):
        insufficient.append("runbook_walkthrough_incomplete")

    if blockers:
        verdict = "NO_GO"
    elif insufficient:
        verdict = "INSUFFICIENT_EVIDENCE"
    else:
        verdict = "GO"

    return {
        "verdict": verdict,
        "blockers": blockers,
        "insufficient_evidence": insufficient,
        "passed_items": passed,
        "evaluated_at": datetime.now(UTC).isoformat(),
        "scoped_external_onboarding": verdict == "GO",
        "ga_ready": False,
    }
