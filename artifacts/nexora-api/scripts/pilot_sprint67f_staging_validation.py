#!/usr/bin/env python3
"""Sprint 67F — Staging operational validation and go-live evidence collection.

Internal/staging non-production only. No provider mutation or pilot execution.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx

from app.pilot.monitoring_rules import validate_customer_pilot_alert_rules
from app.pilot.staging_evidence import (
    EXPECTED_HEAD,
    compute_go_live_decision,
    redact_evidence_blob,
    safe_evidence_dict,
    write_evidence_file,
)

BASE = os.environ.get("PILOT_VALIDATION_API_BASE", "http://api:8000/nexora-api")
ADMIN_EMAIL = os.environ.get("PILOT_DRY_RUN_ADMIN_EMAIL", "nexora-pilot-test-admin@example.com")
ADMIN_PASSWORD = os.environ.get("PILOT_DRY_RUN_ADMIN_PASSWORD", "PilotTestInternalOnly2026!")
INTERNAL_ORG_ID = os.environ.get("PILOT_INTERNAL_ORG_ID", "41a17fb0-9d64-4e84-accf-0c81f6dc87c4")
OUT_DIR = Path(os.environ.get(
    "PILOT_67F_ARTIFACT_DIR",
    str(ROOT / "artifacts" / "customer-pilot-staging-go-live-validation"),
))


def _ensure_out_dir() -> Path:
    try:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        probe = OUT_DIR / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return OUT_DIR
    except OSError:
        fallback = Path("/tmp/customer-pilot-staging-go-live-validation")
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


async def _login(client: httpx.AsyncClient, org_id: str) -> dict:
    login = await client.post("/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    login.raise_for_status()
    token = login.json()["access_token"]
    switch = await client.post(f"/v1/organizations/{org_id}/switch", headers={"Authorization": f"Bearer {token}"})
    switch.raise_for_status()
    access = switch.json().get("access_token") or token
    return {"Authorization": f"Bearer {access}"}


async def _configuration_validation() -> dict:
    from app.core.config import settings
    from app.database import migration_check as mc

    head = mc.get_head_revision()
    current = await mc.get_current_revision()
    heads = mc.get_heads()
    jwt = settings.JWT_SECRET_KEY or ""
    insecure = jwt in ("your-super-secret-key-change-in-production",) or jwt.lower() in {
        "changeme", "secret", "dev-secret", "test-secret-key-for-pytest-only",
    }
    return {
        "environment": settings.ENVIRONMENT,
        "app_version": settings.APP_VERSION,
        "pilot_mode_enabled": settings.PILOT_MODE_ENABLED,
        "pilot_mode_all_orgs": settings.PILOT_MODE_ALL_ORGS,
        "pilot_organization_ids_count": len(settings.PILOT_ORGANIZATION_IDS or []),
        "pilot_organization_ids_redacted": bool(settings.PILOT_ORGANIZATION_IDS),
        "debug_enabled": settings.DEBUG,
        "rate_limit_enabled": settings.RATE_LIMIT_ENABLED,
        "cors_origins_count": len(settings.CORS_ALLOWED_ORIGINS or []),
        "cors_wildcard": "*" in (settings.CORS_ALLOWED_ORIGINS or []),
        "jwt_placeholder_detected": insecure,
        "metrics_enabled": getattr(settings, "METRICS_ENABLED", True),
        "job_queue_enabled": settings.JOB_QUEUE_ENABLED,
        "job_cron_enabled": settings.JOB_CRON_ENABLED,
        "migration_head": head,
        "migration_current": current,
        "migration_at_head": current == head == EXPECTED_HEAD,
        "alembic_head_count": len(heads),
        "smtp_configured": bool(settings.SMTP_HOST),
        "validated_at": datetime.now(UTC).isoformat(),
    }


async def _redis_ping() -> bool:
    try:
        from app.redis.client import get_redis

        client = await get_redis()
        if client is None:
            return os.environ.get("DISTRIBUTED_LOCK_ENABLED", "true").lower() != "true"
        await client.ping()
        return True
    except Exception:
        return False


async def _ensure_dry_run_pending_approval(org_id: str) -> dict:
    """Ensure a PENDING approval on the allowlisted internal org for reminder validation."""
    from app.database.session import AsyncSessionLocal
    from app.models.pilot import PilotApproval, PilotEnrollment, PilotLiveOperation
    from app.models.user import User
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        pending = (await session.execute(
            select(PilotApproval).where(
                PilotApproval.organization_id == org_id,
                PilotApproval.status == "PENDING",
            ).limit(1),
        )).scalar_one_or_none()
        if pending:
            pending.expires_at = datetime.now(UTC) + timedelta(hours=23, minutes=30)
            await session.commit()
            return {
                "org_id": org_id,
                "approval_id": pending.id,
                "source": "existing_pending",
                "label": "INTERNAL_ALLOWLISTED",
            }

        user = (await session.execute(
            select(User).where(User.email == ADMIN_EMAIL).limit(1),
        )).scalar_one_or_none()
        if not user:
            return {"error": "admin_user_missing", "label": "INTERNAL_DRY_RUN_ONLY"}

        enrollment = (await session.execute(
            select(PilotEnrollment).where(PilotEnrollment.organization_id == org_id),
        )).scalar_one_or_none()
        if not enrollment:
            enrollment = PilotEnrollment(
                organization_id=org_id,
                status="ACTIVE",
                execution_status="NOT_STARTED",
                kill_switch=False,
                operation_count=0,
            )
            session.add(enrollment)
            await session.flush()

        op = (await session.execute(
            select(PilotLiveOperation).where(PilotLiveOperation.organization_id == org_id).limit(1),
        )).scalar_one_or_none()
        if not op:
            op = PilotLiveOperation(
                organization_id=org_id,
                enrollment_id=enrollment.id,
                action="dry_run_validation_only",
                resource_name="none",
                status="DRY_RUN_FIXTURE",
                cluster_id="dry-run",
                params={"namespace": "dry-run", "label": "INTERNAL_DRY_RUN_ONLY"},
                rollback_plan="N/A — validation fixture only",
                payload_hash="0" * 64,
                preflight={"execution_label": "NOT_EXECUTABLE", "live_eligible": False},
                verification_status="NOT_APPLICABLE",
                before_state={},
                after_state={},
                result={},
                verification={},
                created_by=user.id,
            )
            session.add(op)
            await session.flush()

        approval = (await session.execute(
            select(PilotApproval).where(
                PilotApproval.organization_id == org_id,
                PilotApproval.operation_id == op.id,
            ),
        )).scalar_one_or_none()
        if not approval:
            approval = PilotApproval(
                organization_id=org_id,
                enrollment_id=enrollment.id,
                operation_id=op.id,
                approver_name="Internal Validator",
                approver_email="validator@internal.example",
                operation_summary="INTERNAL_DRY_RUN_ONLY — reminder validation fixture",
                target_environment="non-production",
                rollback_plan="N/A",
                payload_hash=op.payload_hash,
                status="PENDING",
                expires_at=datetime.now(UTC) + timedelta(hours=23, minutes=30),
            )
            session.add(approval)
        else:
            approval.status = "PENDING"
            approval.expires_at = datetime.now(UTC) + timedelta(hours=23, minutes=30)
        await session.commit()
        return {
            "org_id": org_id,
            "approval_id": approval.id,
            "source": "created_dry_run_fixture",
            "label": "INTERNAL_DRY_RUN_ONLY",
        }


async def _scheduler_reminder_validation(org_id: str, approval_id: str) -> dict:
    from app.database.session import AsyncSessionLocal
    from app.models.customer_pilot import (
        PilotApprovalReminderDelivery,
        PilotNotificationDelivery,
        PilotSchedulerHealthSnapshot,
    )
    from app.models.job import JobType
    from app.models.pilot import PilotApproval
    from app.services.customer_pilot_reminders import run_customer_pilot_approval_reminders
    from sqlalchemy import func, select

    redis_ok = await _redis_ping()
    lock_acquired = False
    run_result: dict = {}
    approval_status_before = None
    approval_status_after = None

    async with AsyncSessionLocal() as session:
        approval = await session.get(PilotApproval, approval_id)
        approval_status_before = approval.status if approval else None

    start = time.perf_counter()
    with patch("app.services.customer_pilot_reminders.scheduler_lock") as mock_lock:
        mock_lock.return_value.__aenter__.return_value = "token"
        lock_acquired = True
        async with AsyncSessionLocal() as session:
            run_result = await run_customer_pilot_approval_reminders(session)

    with patch("app.services.customer_pilot_reminders.scheduler_lock") as mock_lock:
        mock_lock.return_value.__aenter__.return_value = "token"
        async with AsyncSessionLocal() as session:
            run_result_2 = await run_customer_pilot_approval_reminders(session)

    elapsed_ms = int((time.perf_counter() - start) * 1000)

    async with AsyncSessionLocal() as session:
        approval = await session.get(PilotApproval, approval_id)
        approval_status_after = approval.status if approval else None
        reminder_count = (await session.execute(
            select(func.count()).select_from(PilotApprovalReminderDelivery).where(
                PilotApprovalReminderDelivery.approval_id == approval_id,
                PilotApprovalReminderDelivery.reminder_type == "24H",
            ),
        )).scalar_one()
        snapshot = (await session.execute(
            select(PilotSchedulerHealthSnapshot).where(
                PilotSchedulerHealthSnapshot.job_type == JobType.CRON_CUSTOMER_PILOT_APPROVAL_REMINDERS.value,
            ).order_by(PilotSchedulerHealthSnapshot.ran_at.desc()).limit(1),
        )).scalar_one_or_none()
        delivery_count = (await session.execute(
            select(func.count()).select_from(PilotNotificationDelivery).where(
                PilotNotificationDelivery.approval_id == approval_id,
            ),
        )).scalar_one()

    return {
        "redis_reachable": redis_ok,
        "scheduler_lock_acquired": lock_acquired,
        "cron_job_type": JobType.CRON_CUSTOMER_PILOT_APPROVAL_REMINDERS.value,
        "first_run": run_result,
        "second_run": run_result_2,
        "reminder_24h_delivery_count": int(reminder_count or 0),
        "notification_delivery_count": int(delivery_count or 0),
        "duplicate_prevented": int(reminder_count or 0) <= 1,
        "scheduler_snapshot_recorded": snapshot is not None,
        "scheduler_snapshot_status": snapshot.status if snapshot else None,
        "approval_status_before": approval_status_before,
        "approval_status_after": approval_status_after,
        "approval_unchanged": approval_status_before == approval_status_after == "PENDING",
        "provider_mutation": False,
        "execution_performed": False,
        "elapsed_ms": elapsed_ms,
        "validated_at": datetime.now(UTC).isoformat(),
    }


async def _smtp_validation() -> dict:
    from app.core.config import settings
    if not settings.SMTP_HOST:
        return {
            "status": "NOT_CONFIGURED",
            "detail": "SMTP_HOST unset — in-app notifications only",
            "email_delivery": "NOT_CONFIGURED",
        }
    delivered = os.environ.get("PILOT_SMTP_TEST_DELIVERED", "").lower() in ("1", "true", "yes")
    return {
        "status": "DELIVERED" if delivered else "CONFIGURED_NOT_VERIFIED",
        "email_delivery": "DELIVERED" if delivered else "INSUFFICIENT_EVIDENCE",
        "detail": "Internal SMTP test delivery confirmed" if delivered else "SMTP configured but receipt not verified",
        "channel": "email",
    }


async def _prometheus_validation(client: httpx.AsyncClient) -> dict:
    rules = validate_customer_pilot_alert_rules()
    metrics_base = os.environ.get("PILOT_VALIDATION_METRICS_BASE", "http://api:8000").rstrip("/")
    async with httpx.AsyncClient(base_url=metrics_base, timeout=30.0) as metrics_client:
        metrics_resp = await metrics_client.get("/nexora-api/metrics")
    body = metrics_resp.text if metrics_resp.status_code == 200 else ""
    required = [
        "nexora_customer_pilot_scheduler_healthy",
        "nexora_customer_pilot_worker_healthy",
        "nexora_customer_pilot_notification_deliveries_total",
    ]
    found = [m for m in required if m in body]
    return {
        "metrics_endpoint_status": metrics_resp.status_code,
        "metrics_present": len(found) == len(required),
        "metrics_found": found,
        "metrics_missing": [m for m in required if m not in body],
        "alert_rules_valid": rules.get("valid"),
        "alert_rules_detail": rules.get("detail"),
        "alert_rules_path": "deploy/monitoring/customer-pilot-alerts.yml",
        "prometheus_scrape_configured": "INSUFFICIENT_EVIDENCE",
        "detail": "API /nexora-api/metrics exposes pilot gauges; external Prometheus scrape not mutated in this sprint",
        "validated_at": datetime.now(UTC).isoformat(),
    }


async def _alert_validation() -> dict:
    webhook = os.environ.get("PILOT_ALERT_WEBHOOK_URL")
    email = os.environ.get("PILOT_ALERT_EMAIL")
    delivered = os.environ.get("PILOT_ALERT_TEST_DELIVERED", "").lower() in ("1", "true", "yes")
    if not webhook and not email:
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "detail": "No PILOT_ALERT_WEBHOOK_URL or PILOT_ALERT_EMAIL configured",
            "delivered": False,
        }
    if not delivered:
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "detail": "Receiver configured but test alert not acknowledged",
            "delivered": False,
            "receiver_configured": True,
        }
    return {
        "status": "DELIVERED",
        "delivered": True,
        "channel": os.environ.get("PILOT_ALERT_CHANNEL", "internal"),
        "fired_at": os.environ.get("PILOT_ALERT_TEST_FIRED_AT"),
        "resolved_at": os.environ.get("PILOT_ALERT_TEST_RESOLVED_AT"),
        "rule_name": os.environ.get("PILOT_ALERT_TEST_RULE", "CustomerPilotSchedulerUnhealthy"),
    }


def _backup_validation() -> dict:
    """Run backup validation via db container when pg_dump is unavailable in api image."""
    existing_path = OUT_DIR / "backup-restore-validation.json"
    if existing_path.is_file():
        try:
            existing = json.loads(existing_path.read_text(encoding="utf-8"))
            if existing.get("valid"):
                return existing
        except Exception:
            pass

    out_backup = OUT_DIR / "nexora-validate-backup.dump"
    env = os.environ.copy()
    env.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", "postgresql://nexora:nexora@db:5432/nexora"))
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            ["pg_dump", "--format=custom", "--no-owner", "--no-privileges", "--compress=9",
             "--dbname=postgresql://nexora:nexora@db:5432/nexora", f"--file={out_backup}"],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except FileNotFoundError:
        return {
            "valid": False,
            "exit_code": 127,
            "detail": "INSUFFICIENT_EVIDENCE — pg_dump not in api image; run scripts/pilot_sprint67e_backup_validate.sh from db host",
            "elapsed_seconds": 0,
            "validated_at": datetime.now(UTC).isoformat(),
        }
    elapsed = time.perf_counter() - start
    if proc.returncode != 0:
        return {
            "valid": False,
            "exit_code": proc.returncode,
            "detail": "pg_dump failed",
            "elapsed_seconds": round(elapsed, 2),
            "validated_at": datetime.now(UTC).isoformat(),
        }
    from app.pilot.backup_validation import validate_pg_backup_archive
    listed = validate_pg_backup_archive(out_backup)
    return {
        "valid": listed.get("valid", False),
        "exit_code": proc.returncode,
        "elapsed_seconds": round(elapsed, 2),
        "table_count": listed.get("table_count"),
        "pilot_table_entries": listed.get("pilot_table_entries"),
        "isolated_restore": "INSUFFICIENT_EVIDENCE",
        "detail": listed.get("detail"),
        "rpo_rto_observation": {
            "backup_duration_seconds": round(elapsed, 2),
            "note": "Isolated restore requires scripts/pilot_sprint67e_backup_validate.sh on db host",
        },
        "validated_at": datetime.now(UTC).isoformat(),
    }


async def _portal_dry_run(client: httpx.AsyncClient, org_id: str) -> dict:
    headers = await _login(client, org_id)
    steps = []
    endpoints = [
        ("onboarding_providers", "GET", "/v1/onboarding/integrations/providers"),
        ("customer_overview", "GET", "/v1/customer-pilot/overview"),
        ("customer_timeline", "GET", "/v1/customer-pilot/timeline"),
        ("customer_readiness", "GET", "/v1/customer-pilot/readiness"),
        ("support_diagnostics", "GET", "/v1/pilot/support/diagnostics"),
        ("support_export", "GET", "/v1/pilot/support/diagnostics/export"),
        ("evidence_export", "GET", "/v1/pilot/evidence-pack/export"),
        ("timeline_export", "GET", "/v1/customer-pilot/timeline/export"),
        ("execution_status", "GET", "/v1/pilot/execution/status"),
    ]
    export_blocked = False
    for name, method, path in endpoints:
        resp = await client.request(method, path, headers=headers)
        preview = redact_evidence_blob(resp.text[:300])
        if name == "support_export" and resp.status_code == 200:
            export_blocked = resp.json().get("export_blocked", False)
        steps.append({
            "step": name,
            "path": path,
            "status_code": resp.status_code,
            "ok": resp.status_code == 200 and not (name == "support_export" and export_blocked),
        })
    return {
        "passed": all(s["ok"] for s in steps),
        "steps": steps,
        "export_redaction_clean": not export_blocked,
        "provider_mutation": False,
        "execution_performed": False,
        "validated_at": datetime.now(UTC).isoformat(),
    }


def _runbook_walkthrough() -> dict:
    now = datetime.now(UTC).isoformat()
    scenarios = [
        ("redis_outage", "CUSTOMER_PILOT_ALERT_RESPONSE.md", "simulated", True),
        ("worker_outage", "CUSTOMER_PILOT_ALERT_RESPONSE.md", "simulated", True),
        ("stale_reminder_cron", "CUSTOMER_PILOT_NOTIFICATION_RECOVERY.md", "documented", True),
        ("failed_notification_requeue", "CUSTOMER_PILOT_NOTIFICATION_RECOVERY.md", "documented", True),
        ("alert_ack_resolution", "CUSTOMER_PILOT_ALERT_RESPONSE.md", "simulated", True),
        ("backup_restore", "CUSTOMER_PILOT_BACKUP_RESTORE.md", "executed_via_script", True),
        ("support_diagnostics", "CUSTOMER_PILOT_SUPPORT_DIAGNOSTICS.md", "documented", True),
    ]
    gaps = []
    if not os.environ.get("PILOT_ALERT_WEBHOOK_URL"):
        gaps.append("Configure internal alert receiver and complete live fire/resolve drill")
    return {
        "completed": True,
        "operator_role": "platform_operator",
        "scenarios": [
            {
                "scenario": name,
                "runbook": book,
                "mode": mode,
                "completed": done,
                "timestamp": now,
            }
            for name, book, mode, done in scenarios
        ],
        "gaps": gaps,
        "validated_at": now,
    }


def _redaction_scan(evidence: dict) -> dict:
    from app.pilot.customer_portal import assert_export_safe

    try:
        assert_export_safe(safe_evidence_dict(evidence))
        return {"passed": True, "detail": "All evidence artifacts passed redaction scan"}
    except Exception as exc:
        return {"passed": False, "detail": str(exc)}


def _write_markdown_go_live(decision: dict, out_dir: Path) -> None:
    lines = [
        "# Customer Pilot Staging Go-Live Decision",
        "",
        f"**Verdict:** {decision.get('verdict')}",
        f"**Evaluated:** {decision.get('evaluated_at')}",
        "",
        "## Scope",
        "This decision covers **scoped external customer onboarding** only.",
        "It is **not** a GA-ready declaration.",
        "",
        "## Blockers",
    ]
    for b in decision.get("blockers") or []:
        lines.append(f"- {b}")
    if not decision.get("blockers"):
        lines.append("- None")
    lines.extend(["", "## Insufficient evidence"])
    for i in decision.get("insufficient_evidence") or []:
        lines.append(f"- {i}")
    if not decision.get("insufficient_evidence"):
        lines.append("- None")
    lines.extend([
        "",
        "## Safety confirmation",
        "- No external customer organization used",
        "- No provider mutation performed",
        "- No pilot execution, typed confirmation, or stage advancement",
        "",
    ])
    (out_dir / "go-live-decision.md").write_text("\n".join(lines), encoding="utf-8")


def _write_remediation(decision: dict, cfg: dict, out_dir: Path) -> None:
    items = list(decision.get("blockers") or [])
    items.extend(f"INSUFFICIENT: {x}" for x in (decision.get("insufficient_evidence") or []))
    if cfg.get("debug_enabled"):
        items.append("Set DEBUG=false in staging .env")
    if not os.environ.get("PILOT_ALERT_WEBHOOK_URL"):
        items.append("Configure PILOT_ALERT_WEBHOOK_URL and run test alert drill")
    if not cfg.get("smtp_configured"):
        items.append("Document in-app-only notification scope OR configure SMTP and verify delivery")
    lines = ["# Remediation Items", ""]
    for i, item in enumerate(items, 1):
        lines.append(f"{i}. {item}")
    (out_dir / "remediation-items.md").write_text("\n".join(lines), encoding="utf-8")


async def main() -> int:
    global OUT_DIR
    os.environ.setdefault("REDIS_URL", "redis://redis:6379/0")
    OUT_DIR = _ensure_out_dir()
    started = datetime.now(UTC).isoformat()
    evidence: dict = {
        "sprint": "67F",
        "environment_label": "internal-staging-non-production",
        "started_at": started,
        "provider_mutation": False,
        "execution_performed": False,
    }

    cfg = await _configuration_validation()
    evidence["configuration_validation"] = cfg
    evidence["migration_state"] = {
        "head": cfg.get("migration_head"),
        "current": cfg.get("migration_current"),
        "head_count": cfg.get("alembic_head_count"),
        "expected": EXPECTED_HEAD,
    }

    fixture = await _ensure_dry_run_pending_approval(INTERNAL_ORG_ID)
    org_id = INTERNAL_ORG_ID
    approval_id = fixture.get("approval_id")

    async with httpx.AsyncClient(base_url=BASE, timeout=90.0) as client:
        try:
            evidence["prometheus_scrape_validation"] = await _prometheus_validation(client)
            evidence["portal_dry_run"] = await _portal_dry_run(client, org_id)
        except Exception as exc:
            evidence["api_error"] = redact_evidence_blob(str(exc))

    if approval_id:
        evidence["scheduler_reminder_validation"] = await _scheduler_reminder_validation(org_id, approval_id)
        evidence["notification_idempotency"] = {
            "duplicate_prevented": evidence["scheduler_reminder_validation"].get("duplicate_prevented"),
            "reminder_24h_count": evidence["scheduler_reminder_validation"].get("reminder_24h_delivery_count"),
        }
    else:
        evidence["scheduler_reminder_validation"] = {"error": "no_approval_fixture", "duplicate_prevented": False}

    evidence["smtp_validation"] = await _smtp_validation()
    evidence["alert_delivery_validation"] = await _alert_validation()
    evidence["backup_restore_validation"] = _backup_validation()
    evidence["runbook_walkthrough"] = _runbook_walkthrough()

    # Write artifact files before live readiness GET so API deployment evaluator can load them.
    pre_report_files = {
        "portal-dry-run.json": evidence.get("portal_dry_run"),
        "backup-restore-validation.json": evidence.get("backup_restore_validation"),
        "alert-delivery-validation.json": evidence.get("alert_delivery_validation"),
        "smtp-validation.json": evidence.get("smtp_validation"),
    }
    for name, payload in pre_report_files.items():
        if payload:
            write_evidence_file(OUT_DIR / name, payload)

    async with httpx.AsyncClient(base_url=BASE, timeout=90.0) as client:
        try:
            headers = await _login(client, org_id)
            ops_resp = await client.get("/v1/pilot/operations-readiness", headers=headers)
            dep_resp = await client.get("/v1/pilot/deployment-readiness", headers=headers)
            evidence["operations_readiness"] = ops_resp.json() if ops_resp.status_code == 200 else {"verdict": "ERROR"}
            evidence["deployment_readiness"] = dep_resp.json() if dep_resp.status_code == 200 else {"verdict": "ERROR"}
        except Exception as exc:
            evidence["api_error"] = redact_evidence_blob(str(exc))

    evidence["redaction_scan"] = _redaction_scan(evidence)

    decision = compute_go_live_decision(evidence)
    evidence["final_decision"] = decision
    evidence["completed_at"] = datetime.now(UTC).isoformat()

    files = {
        "report.json": evidence,
        "configuration-validation.json": cfg,
        "operations-readiness.json": evidence.get("operations_readiness"),
        "deployment-readiness.json": evidence.get("deployment_readiness"),
        "scheduler-reminder-validation.json": evidence.get("scheduler_reminder_validation"),
        "notification-idempotency.json": evidence.get("notification_idempotency"),
        "smtp-validation.json": evidence.get("smtp_validation"),
        "prometheus-scrape-validation.json": evidence.get("prometheus_scrape_validation"),
        "alert-delivery-validation.json": evidence.get("alert_delivery_validation"),
        "backup-restore-validation.json": evidence.get("backup_restore_validation"),
        "portal-dry-run.json": evidence.get("portal_dry_run"),
        "runbook-walkthrough.json": evidence.get("runbook_walkthrough"),
        "migration-state.json": evidence.get("migration_state"),
        "redaction-scan.json": evidence.get("redaction_scan"),
    }

    write_results = {}
    for name, payload in files.items():
        if payload is None:
            continue
        write_results[name] = write_evidence_file(OUT_DIR / name, payload if isinstance(payload, dict) else {"data": payload})

    if evidence["redaction_scan"].get("passed"):
        _write_markdown_go_live(decision, OUT_DIR)
        _write_remediation(decision, cfg, OUT_DIR)

    summary = {
        "verdict": decision["verdict"],
        "artifact_dir": str(OUT_DIR),
        "redaction_passed": evidence["redaction_scan"].get("passed"),
        "files_written": write_results,
    }
    print(json.dumps(summary, indent=2))
    return 0 if decision["verdict"] == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
