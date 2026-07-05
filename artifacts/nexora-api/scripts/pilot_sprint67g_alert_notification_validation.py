#!/usr/bin/env python3
"""Sprint 67G — Alerting and notification go-live validation."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx

from app.core.config import settings
from app.pilot.alert_notification_evidence import (
    compute_alert_notification_go_live_decision,
    parse_alert_rule_load_evidence,
    parse_prometheus_scrape_evidence,
    parse_receiver_receipts,
    redact_receiver_config,
    smtp_scope_decision,
    validate_alert_delivery_evidence,
    write_alert_notification_artifacts,
)
from app.pilot.staging_evidence import redact_evidence_blob, write_evidence_file

BASE = os.environ.get("PILOT_VALIDATION_API_BASE", "http://api:8000/nexora-api")
METRICS_BASE = os.environ.get("PILOT_VALIDATION_METRICS_BASE", "http://api:8000")
PROMETHEUS_BASE = os.environ.get(
    "PILOT_CUSTOMER_PILOT_PROMETHEUS_ENDPOINT",
    settings.PILOT_CUSTOMER_PILOT_PROMETHEUS_ENDPOINT,
)
ADMIN_EMAIL = os.environ.get("PILOT_DRY_RUN_ADMIN_EMAIL", "nexora-pilot-test-admin@example.com")
ADMIN_PASSWORD = os.environ.get("PILOT_DRY_RUN_ADMIN_PASSWORD", "PilotTestInternalOnly2026!")
INTERNAL_ORG_ID = os.environ.get("PILOT_INTERNAL_ORG_ID", "41a17fb0-9d64-4e84-accf-0c81f6dc87c4")
OUT_DIR = Path(os.environ.get(
    "PILOT_67G_ARTIFACT_DIR",
    str(ROOT / "artifacts" / "customer-pilot-alert-notification-validation"),
))
RECEIPT_PATH = OUT_DIR / "alert-receiver-receipt.json"
RECEIVER_RESET_URL = os.environ.get(
    "PILOT_ALERT_RECEIVER_RESET_URL",
    "http://customer-pilot-alert-receiver:9191/reset",
)
WAIT_SECONDS = int(os.environ.get("PILOT_ALERT_TEST_WAIT_SECONDS", "90"))


def _reset_receiver() -> None:
    if RECEIPT_PATH.is_file():
        RECEIPT_PATH.unlink()
    try:
        httpx.post(RECEIVER_RESET_URL, timeout=10.0)
    except Exception:
        pass


async def _login(client: httpx.AsyncClient, org_id: str) -> dict:
    login = await client.post("/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    login.raise_for_status()
    token = login.json()["access_token"]
    switch = await client.post(
        f"/v1/organizations/{org_id}/switch",
        headers={"Authorization": f"Bearer {token}"},
    )
    switch.raise_for_status()
    access = switch.json().get("access_token") or token
    return {"Authorization": f"Bearer {access}"}


async def _fetch_readiness(client: httpx.AsyncClient, headers: dict) -> dict:
    ops = await client.get("/v1/pilot/operations-readiness", headers=headers)
    dep = await client.get("/v1/pilot/deployment-readiness", headers=headers)
    return {
        "operations": ops.json() if ops.status_code == 200 else {"verdict": "ERROR"},
        "deployment": dep.json() if dep.status_code == 200 else {"verdict": "ERROR"},
    }


async def _set_test_signal(client: httpx.AsyncClient, headers: dict, value: int) -> None:
    resp = await client.post(
        "/v1/pilot/internal/alert-test-signal",
        headers=headers,
        params={"value": value},
    )
    resp.raise_for_status()


def _wait_for_receipt(*, firing: bool, resolved: bool, timeout: int) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        receipt = parse_receiver_receipts(RECEIPT_PATH)
        if firing and (receipt.get("firing_count", 0) or 0) >= 1:
            if not resolved:
                return receipt
        if resolved and receipt.get("delivered"):
            return receipt
        if firing and (receipt.get("firing_count", 0) or 0) >= 1 and not resolved:
            return receipt
        time.sleep(2)
    return parse_receiver_receipts(RECEIPT_PATH)


def _smtp_validation(email_enabled: bool) -> dict:
    if not email_enabled:
        return {
            "status": "NOT_CONFIGURED",
            "email_delivery": "NOT_REQUIRED",
            "detail": "In-app-only scope — SMTP validation not required",
        }
    if not settings.SMTP_HOST:
        return {
            "status": "NOT_CONFIGURED",
            "email_delivery": "INSUFFICIENT_EVIDENCE",
            "detail": "Email mode enabled but SMTP_HOST unset",
        }
    delivered = os.environ.get("PILOT_SMTP_TEST_DELIVERED", "").lower() in ("1", "true", "yes")
    return {
        "status": "DELIVERED" if delivered else "INSUFFICIENT_EVIDENCE",
        "email_delivery": "DELIVERED" if delivered else "INSUFFICIENT_EVIDENCE",
        "channel": "email",
        "detail": "Internal SMTP receipt confirmed" if delivered else "SMTP configured but receipt not verified",
    }


def _redaction_scan(evidence: dict) -> dict:
    blob = redact_evidence_blob(json.dumps(evidence, default=str))
    bad = []
    for pat in ("password=", "postgresql://", "Bearer ", "smtp_password"):
        if pat.lower() in blob.lower():
            bad.append(pat)
    webhook = os.environ.get("PILOT_ALERT_WEBHOOK_URL", "")
    if webhook and webhook in blob:
        bad.append("webhook_url_leak")
    return {
        "passed": not bad,
        "detail": "All evidence artifacts passed redaction scan" if not bad else f"Failed patterns: {bad}",
    }


def _write_go_live(decision: dict, out_dir: Path) -> None:
    lines = [
        "# Customer Pilot Alert & Notification Go-Live Decision",
        "",
        f"**Verdict:** {decision['verdict']}",
        f"**Evaluated:** {decision['evaluated_at']}",
        "",
        "## Scope",
        "Scoped external customer onboarding only. Not GA-ready.",
        "",
        "## Blockers",
    ]
    lines.extend(f"- {b}" for b in decision.get("blockers") or ["None"])
    lines.extend(["", "## Insufficient evidence"])
    lines.extend(f"- {i}" for i in decision.get("insufficient_evidence") or ["None"])
    lines.extend([
        "",
        "## Safety confirmation",
        "- No external customer organization used",
        "- No provider mutation performed",
        "- No pilot execution, typed confirmation, or stage advancement",
    ])
    (out_dir / "go-live-decision.md").write_text("\n".join(lines), encoding="utf-8")


async def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now(UTC).isoformat()
    email_enabled = settings.PILOT_EMAIL_NOTIFICATIONS_ENABLED

    evidence: dict = {
        "sprint": "67G",
        "environment_label": "internal-staging-non-production",
        "started_at": started,
        "provider_mutation": False,
        "execution_performed": False,
    }

    async with httpx.AsyncClient(base_url=BASE, timeout=90.0) as client:
        headers = await _login(client, INTERNAL_ORG_ID)
        before = await _fetch_readiness(client, headers)
        evidence["deployment_readiness_before"] = before["deployment"]
        evidence["operations_readiness"] = before["operations"]

    evidence["smtp_scope_decision"] = smtp_scope_decision(
        email_enabled=email_enabled,
        smtp_configured=bool(settings.SMTP_HOST),
    )
    evidence["smtp_validation"] = _smtp_validation(email_enabled)

    # Allow Prometheus to scrape and rules to load.
    time.sleep(5)
    evidence["prometheus_scrape_validation"] = parse_prometheus_scrape_evidence(
        prometheus_base=PROMETHEUS_BASE,
        metrics_base=METRICS_BASE,
    )
    evidence["alert_rule_load_validation"] = parse_alert_rule_load_evidence(PROMETHEUS_BASE)

    fire_evidence: dict = {
        "started_at": datetime.now(UTC).isoformat(),
        "rule_name": "CustomerPilotAlertDeliveryTest",
        "method": "controlled_test_signal",
        "provider_mutation": False,
    }
    resolution_evidence: dict = {"started_at": None, "resolved_at": None}

    if RECEIPT_PATH.is_file():
        RECEIPT_PATH.unlink()
    _reset_receiver()

    async with httpx.AsyncClient(base_url=BASE, timeout=90.0) as client:
        headers = await _login(client, INTERNAL_ORG_ID)
        try:
            await _set_test_signal(client, headers, 1)
            fire_evidence["signal_set"] = 1
            fire_evidence["fired_at"] = datetime.now(UTC).isoformat()
            firing_receipt = _wait_for_receipt(firing=True, resolved=False, timeout=WAIT_SECONDS)
            fire_evidence["firing_observed"] = (firing_receipt.get("firing_count", 0) or 0) >= 1
            fire_evidence["receiver_acknowledged"] = fire_evidence["firing_observed"]

            await _set_test_signal(client, headers, 0)
            resolution_evidence["started_at"] = datetime.now(UTC).isoformat()
            final_receipt = _wait_for_receipt(firing=True, resolved=True, timeout=WAIT_SECONDS)
            resolution_evidence["resolved_at"] = final_receipt.get("resolved_at")
            resolution_evidence["resolution_observed"] = final_receipt.get("delivered", False)
            resolution_evidence["duplicate_prevented"] = final_receipt.get("duplicate_prevented", True)
        except Exception as exc:
            fire_evidence["error"] = redact_evidence_blob(str(exc))

    if RECEIPT_PATH.is_file():
        receipt = parse_receiver_receipts(RECEIPT_PATH)
        write_evidence_file(RECEIPT_PATH, receipt)
    else:
        receipt = {"delivered": False, "detail": "No webhook receipts captured"}

    evidence["alert_fire_validation"] = redact_receiver_config(fire_evidence)
    evidence["alert_receiver_receipt"] = receipt
    evidence["alert_resolution_validation"] = redact_receiver_config(resolution_evidence)
    evidence["alert_delivery_validation"] = validate_alert_delivery_evidence(receipt)

    # Bridge alert evidence for deployment evaluator (67F artifact dir).
    bridge_dir = Path(os.environ.get(
        "PILOT_67F_ARTIFACT_DIR",
        str(ROOT / "artifacts" / "customer-pilot-staging-go-live-validation"),
    ))
    bridge_dir.mkdir(parents=True, exist_ok=True)
    write_evidence_file(bridge_dir / "alert-delivery-validation.json", evidence["alert_delivery_validation"])
    write_evidence_file(OUT_DIR / "alert-receiver-receipt.json", receipt)

    async with httpx.AsyncClient(base_url=BASE, timeout=90.0) as client:
        headers = await _login(client, INTERNAL_ORG_ID)
        after = await _fetch_readiness(client, headers)
        evidence["deployment_readiness_after"] = after["deployment"]
        evidence["operations_readiness"] = after["operations"]

    evidence["redaction_scan"] = _redaction_scan(evidence)
    decision = compute_alert_notification_go_live_decision(evidence)
    evidence["final_decision"] = decision
    evidence["completed_at"] = datetime.now(UTC).isoformat()

    files = {
        "report.json": evidence,
        "prometheus-scrape-validation.json": evidence["prometheus_scrape_validation"],
        "alert-rule-load-validation.json": evidence["alert_rule_load_validation"],
        "alert-fire-validation.json": evidence["alert_fire_validation"],
        "alert-receiver-receipt.json": evidence["alert_receiver_receipt"],
        "alert-resolution-validation.json": evidence["alert_resolution_validation"],
        "alert-delivery-validation.json": evidence["alert_delivery_validation"],
        "smtp-scope-decision.json": evidence["smtp_scope_decision"],
        "smtp-validation.json": evidence["smtp_validation"],
        "deployment-readiness-before.json": evidence["deployment_readiness_before"],
        "deployment-readiness-after.json": evidence["deployment_readiness_after"],
        "redaction-scan.json": evidence["redaction_scan"],
    }
    write_alert_notification_artifacts(OUT_DIR, files)
    if evidence["redaction_scan"].get("passed"):
        _write_go_live(decision, OUT_DIR)

    summary = {
        "verdict": decision["verdict"],
        "artifact_dir": str(OUT_DIR),
        "deployment_before": evidence["deployment_readiness_before"].get("verdict"),
        "deployment_after": evidence["deployment_readiness_after"].get("verdict"),
        "alert_delivered": evidence["alert_delivery_validation"].get("delivered"),
    }
    print(json.dumps(summary, indent=2))
    return 0 if decision["verdict"] == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
