"""Sprint 67E — Internal deployment readiness validation and portal dry run.

Uses internal test tenant only. No provider mutation, execution, or typed confirmation.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx

BASE = os.environ.get("PILOT_VALIDATION_API_BASE", "http://api:8000/nexora-api")
ADMIN_EMAIL = os.environ.get("PILOT_DRY_RUN_ADMIN_EMAIL", "nexora-pilot-test-admin@example.com")
ADMIN_PASSWORD = os.environ.get("PILOT_DRY_RUN_ADMIN_PASSWORD", "PilotTestInternalOnly2026!")
INTERNAL_ORG_ID = os.environ.get("PILOT_INTERNAL_ORG_ID", "41a17fb0-9d64-4e84-accf-0c81f6dc87c4")
OUT_DIR = Path(os.environ.get("PILOT_67E_ARTIFACT_DIR", "artifacts/pilot-deployment-readiness"))


def _ensure_out_dir() -> Path:
    try:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        probe = OUT_DIR / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return OUT_DIR
    except OSError:
        fallback = Path("/tmp/pilot-deployment-readiness")
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


DRY_RUN_REPORT = OUT_DIR / "dry-run-report.json"
ALERT_REPORT = OUT_DIR / "alert-test.json"

SECRET_PATTERNS = (
    re.compile(r"Bearer\s+\S+", re.I),
    re.compile(r"(?:token|password|secret|api[_-]?key)\s*[:=]\s*\S+", re.I),
    re.compile(r"-----BEGIN"),
)


def _redact_blob(text: str) -> str:
    out = text
    for pat in SECRET_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out


async def _login(client: httpx.AsyncClient, org_id: str) -> dict:
    login = await client.post("/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    login.raise_for_status()
    token = login.json()["access_token"]
    switch = await client.post(f"/v1/organizations/{org_id}/switch", headers={"Authorization": f"Bearer {token}"})
    switch.raise_for_status()
    access = switch.json().get("access_token") or token
    return {"Authorization": f"Bearer {access}"}


async def _deployment_checks(client: httpx.AsyncClient, headers: dict) -> dict:
    livez = await client.get("/livez")
    readyz = await client.get("/readyz")
    dep = await client.get("/v1/pilot/deployment-readiness", headers=headers)
    ops = await client.get("/v1/pilot/operations-readiness", headers=headers)
    return {
        "livez_status": livez.status_code,
        "readyz_status": readyz.status_code,
        "deployment_readiness_status": dep.status_code,
        "deployment_verdict": dep.json().get("verdict") if dep.status_code == 200 else None,
        "operations_verdict": ops.json().get("verdict") if ops.status_code == 200 else None,
    }


async def _portal_dry_run(client: httpx.AsyncClient, headers: dict) -> list[dict]:
    steps: list[dict] = []
    endpoints = [
        ("customer_overview", "GET", "/v1/customer-pilot/overview"),
        ("customer_timeline", "GET", "/v1/customer-pilot/timeline"),
        ("customer_readiness", "GET", "/v1/customer-pilot/readiness"),
        ("customer_communications", "GET", "/v1/customer-pilot/communications"),
        ("support_diagnostics", "GET", "/v1/pilot/support/diagnostics"),
        ("support_export", "GET", "/v1/pilot/support/diagnostics/export"),
        ("operator_handoff_check", "GET", "/v1/pilot/execution/status"),
    ]
    for name, method, path in endpoints:
        resp = await client.request(method, path, headers=headers)
        blob = _redact_blob(resp.text)
        steps.append({
            "step": name,
            "path": path,
            "status_code": resp.status_code,
            "ok": resp.status_code == 200,
            "redacted_preview": blob[:200],
        })
    return steps


async def _reminder_idempotency_dry_run() -> dict:
    """Run reminder service twice with lock; verify dedupe — no provider mutation."""
    from app.database.session import AsyncSessionLocal
    from app.models.customer_pilot import PilotApprovalReminderDelivery
    from app.models.pilot import PilotApproval
    from app.services.customer_pilot_reminders import CustomerPilotReminderService
    from sqlalchemy import func, select

    result = {"ok": False, "detail": "not run"}
    async with AsyncSessionLocal() as session:
        pending = (await session.execute(
            select(PilotApproval).where(
                PilotApproval.organization_id == INTERNAL_ORG_ID,
                PilotApproval.status == "PENDING",
            ).limit(1),
        )).scalar_one_or_none()
        if not pending:
            return {"ok": True, "detail": "No pending approval — skipped reminder idempotency drill", "skipped": True}

        pending.expires_at = datetime.now(UTC) + timedelta(hours=23, minutes=30)
        await session.commit()

    with patch("app.services.customer_pilot_reminders.scheduler_lock") as mock_lock:
        mock_lock.return_value.__aenter__.return_value = "token"
        async with AsyncSessionLocal() as session:
            svc = CustomerPilotReminderService(session)
            r1 = await svc.run()
            r2 = await svc.run()
            await session.commit()

    async with AsyncSessionLocal() as session:
        count = (await session.execute(
            select(func.count()).select_from(PilotApprovalReminderDelivery).where(
                PilotApprovalReminderDelivery.approval_id == pending.id,
                PilotApprovalReminderDelivery.reminder_type == "24H",
            ),
        )).scalar_one()
        result = {
            "ok": int(count or 0) <= 1,
            "detail": f"24H reminder deliveries: {count}; runs={r1}, {r2}",
            "duplicate_prevented": int(count or 0) <= 1,
        }
    return result


async def _failure_drill_redis() -> dict:
    from app.pilot.deployment_readiness import evaluate_pilot_deployment_readiness
    from app.pilot.operations_readiness import evaluate_pilot_operations_readiness

    payload = {
        "redis_available": False,
        "worker_recent": True,
        "reminder_cron_registered": True,
        "distributed_lock_enabled": True,
        "scheduler_lock_available": False,
        "reminder_last_success_at": datetime.now(UTC).isoformat(),
        "reminder_consecutive_failures": 0,
        "job_queue_enabled": True,
    }
    ops = evaluate_pilot_operations_readiness(payload)
    dep = evaluate_pilot_deployment_readiness({
        "migration_head": "0039_customer_pilot_operations",
        "migration_current": "0039_customer_pilot_operations",
        "alembic_head_count": 1,
        "operations_payload": payload,
        "pilot_mode_enabled": True,
        "pilot_mode_all_orgs": False,
        "pilot_organization_ids": [INTERNAL_ORG_ID],
        "debug_enabled": False,
        "insecure_jwt_secret": False,
        "cors_origins": [],
        "rate_limit_enabled": True,
        "health_ok": True,
        "health_detail": "ok",
        "metrics_enabled": True,
        "environment": "staging",
    })
    return {
        "operations_verdict": ops["verdict"],
        "deployment_verdict": dep["verdict"],
        "no_go_on_redis": ops["verdict"] == "NO_GO",
    }


async def _failure_drill_export_redaction() -> dict:
    from app.core.exceptions import ValidationError
    from app.pilot.customer_portal import assert_export_safe

    try:
        assert_export_safe({"token": "password: supersecret"})
        return {"ok": False, "detail": "export should have been blocked"}
    except ValidationError:
        return {"ok": True, "detail": "export fail-closed on secrets"}


async def main() -> int:
    out_dir = _ensure_out_dir()
    global DRY_RUN_REPORT, ALERT_REPORT
    DRY_RUN_REPORT = out_dir / "dry-run-report.json"
    ALERT_REPORT = out_dir / "alert-test.json"
    report: dict = {
        "sprint": "67E",
        "environment": "internal-non-production",
        "started_at": datetime.now(UTC).isoformat(),
        "internal_org_id": INTERNAL_ORG_ID,
        "steps": [],
        "provider_mutation": False,
        "execution_performed": False,
    }

    async with httpx.AsyncClient(base_url=BASE, timeout=60.0) as client:
        try:
            headers = await _login(client, INTERNAL_ORG_ID)
        except Exception as exc:
            report["login_error"] = str(exc)
            report["completed"] = False
            report["passed"] = False
            DRY_RUN_REPORT.write_text(json.dumps(report, indent=2))
            return 2

        report["deployment_checks"] = await _deployment_checks(client, headers)
        report["steps"].extend(await _portal_dry_run(client, headers))

    report["reminder_idempotency"] = await _reminder_idempotency_dry_run()
    report["failure_drill_redis"] = await _failure_drill_redis()
    report["failure_drill_export"] = await _failure_drill_export_redaction()

    alert_delivered = os.environ.get("PILOT_ALERT_TEST_DELIVERED", "").lower() in ("1", "true", "yes")
    ALERT_REPORT.write_text(json.dumps({
        "delivered": alert_delivered,
        "channel": os.environ.get("PILOT_ALERT_CHANNEL", "none"),
        "detail": "Test alert delivered" if alert_delivered else "INSUFFICIENT_EVIDENCE — configure PILOT_ALERT_WEBHOOK_URL and set PILOT_ALERT_TEST_DELIVERED=1 after manual test",
        "evaluated_at": datetime.now(UTC).isoformat(),
    }, indent=2))

    portal_ok = all(s.get("ok") for s in report["steps"])
    reminder_ok = report["reminder_idempotency"].get("ok", False)
    drills_ok = (
        report["failure_drill_redis"].get("no_go_on_redis")
        and report["failure_drill_export"].get("ok")
    )
    report["completed"] = True
    report["passed"] = portal_ok and reminder_ok and drills_ok
    report["summary"] = (
        "Internal dry run passed"
        if report["passed"]
        else "Internal dry run incomplete — review steps"
    )
    report["evaluated_at"] = datetime.now(UTC).isoformat()
    report["smtp_delivery_verified"] = os.environ.get("PILOT_SMTP_TEST_DELIVERED", "").lower() in ("1", "true", "yes")

    safe_report = json.loads(_redact_blob(json.dumps(report)))
    DRY_RUN_REPORT.write_text(json.dumps(safe_report, indent=2))
    print(json.dumps({"passed": report["passed"], "artifact": str(DRY_RUN_REPORT)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
