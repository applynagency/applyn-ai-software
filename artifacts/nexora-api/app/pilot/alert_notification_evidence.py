"""Sprint 67G — Alerting and notification go-live evidence helpers."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from app.pilot.monitoring_rules import (
    REQUIRED_PROMETHEUS_METRICS,
    validate_customer_pilot_alert_rules,
)
from app.pilot.staging_evidence import redact_evidence_blob, write_evidence_file

TEST_ALERT_RULE = "CustomerPilotAlertDeliveryTest"

_SECRET_KEY_PATTERNS = (
    re.compile(r"(?i)webhook[_-]?url"),
    re.compile(r"(?i)password"),
    re.compile(r"(?i)secret"),
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"https?://\S+@\S+"),
)


def redact_receiver_config(data: Any) -> Any:
    """Remove receiver URLs and secrets from evidence payloads."""
    if isinstance(data, dict):
        out = {}
        for key, value in data.items():
            if any(pat.search(str(key)) for pat in _SECRET_KEY_PATTERNS):
                out[key] = "[REDACTED]"
            elif isinstance(value, str) and (
                value.startswith("http://") or value.startswith("https://")
            ):
                out[key] = "[REDACTED_URL]"
            else:
                out[key] = redact_receiver_config(value)
        return out
    if isinstance(data, list):
        return [redact_receiver_config(v) for v in data]
    if isinstance(data, str):
        return redact_evidence_blob(data)
    return data


def parse_prometheus_scrape_evidence(
    *,
    prometheus_base: str,
    metrics_base: str,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Query Prometheus and API metrics endpoints for scrape evidence."""
    prom = prometheus_base.rstrip("/")
    metrics_url = metrics_base.rstrip("/")
    result: dict[str, Any] = {
        "prometheus_endpoint": "[REDACTED_URL]",
        "metrics_endpoint": "[REDACTED_URL]",
        "validated_at": datetime.now(UTC).isoformat(),
    }
    metric_results: dict[str, Any] = {}
    scrape_healthy = False
    try:
        with httpx.Client(timeout=timeout) as client:
            health = client.get(f"{prom}/-/healthy")
            result["prometheus_healthy"] = health.status_code == 200

            targets = client.get(f"{prom}/api/v1/targets")
            if targets.status_code == 200:
                active = targets.json().get("data", {}).get("activeTargets", [])
                api_targets = [
                    t for t in active
                    if "api" in (t.get("labels", {}).get("job", "") or "").lower()
                    or "nexora" in (t.get("labels", {}).get("job", "") or "").lower()
                ]
                if not api_targets:
                    api_targets = active
                scrape_healthy = any(t.get("health") == "up" for t in api_targets)
                result["scrape_targets"] = [
                    {
                        "job": t.get("labels", {}).get("job"),
                        "health": t.get("health"),
                        "last_scrape": t.get("lastScrape"),
                    }
                    for t in api_targets[:5]
                ]

            for metric in REQUIRED_PROMETHEUS_METRICS:
                query = client.get(
                    f"{prom}/api/v1/query",
                    params={"query": metric},
                )
                if query.status_code == 200:
                    series = query.json().get("data", {}).get("result", [])
                    metric_results[metric] = {
                        "present": bool(series),
                        "series_count": len(series),
                    }
                else:
                    metric_results[metric] = {"present": False, "series_count": 0}

            metrics_resp = client.get(f"{metrics_url}/nexora-api/metrics")
            body = metrics_resp.text if metrics_resp.status_code == 200 else ""
            result["metrics_endpoint_status"] = metrics_resp.status_code
            result["metrics_on_api"] = {
                m: m in body for m in REQUIRED_PROMETHEUS_METRICS
            }
    except Exception as exc:
        result["error"] = redact_evidence_blob(str(exc))

    rules = validate_customer_pilot_alert_rules()
    metrics_confirmed = {}
    for metric in REQUIRED_PROMETHEUS_METRICS:
        query_hit = metric_results.get(metric, {}).get("present", False)
        api_hit = result.get("metrics_on_api", {}).get(metric, False)
        metrics_confirmed[metric] = query_hit or (api_hit and scrape_healthy)
    result.update({
        "scrape_healthy": scrape_healthy,
        "metric_query_results": metric_results,
        "metrics_confirmed": metrics_confirmed,
        "metrics_present": scrape_healthy and all(metrics_confirmed.values()),
        "alert_rules_valid": rules.get("valid"),
        "alert_rules_detail": rules.get("detail"),
    })
    return redact_receiver_config(result)


def parse_alert_rule_load_evidence(prometheus_base: str, timeout: float = 30.0) -> dict[str, Any]:
    prom = prometheus_base.rstrip("/")
    local_rules = validate_customer_pilot_alert_rules()
    loaded: list[str] = []
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(f"{prom}/api/v1/rules")
            if resp.status_code == 200:
                for group in resp.json().get("data", {}).get("groups", []):
                    for rule in group.get("rules", []):
                        name = rule.get("name") or rule.get("alert")
                        if name:
                            loaded.append(name)
    except Exception as exc:
        return {
            "valid": False,
            "detail": redact_evidence_blob(str(exc)),
            "validated_at": datetime.now(UTC).isoformat(),
        }
    return redact_receiver_config({
        "valid": local_rules.get("valid") and bool(loaded),
        "detail": "Prometheus rule groups loaded" if loaded else "No rules loaded in Prometheus",
        "alerts_loaded": sorted(set(loaded)),
        "alerts_expected": local_rules.get("alerts_found", []),
        "test_alert_rule": TEST_ALERT_RULE,
        "validated_at": datetime.now(UTC).isoformat(),
    })


def parse_receiver_receipts(receipt_path: Path) -> dict[str, Any]:
    if not receipt_path.is_file():
        return {"delivered": False, "detail": "No receiver receipts recorded"}
    try:
        data = json.loads(receipt_path.read_text(encoding="utf-8"))
    except Exception:
        return {"delivered": False, "detail": "Receiver receipt file unreadable"}
    return redact_receiver_config(data)


def validate_alert_delivery_evidence(receipt: dict[str, Any]) -> dict[str, Any]:
    firing = receipt.get("firing_count", 0) or len(receipt.get("firing_events", []) or [])
    resolved = receipt.get("resolved_count", 0) or len(receipt.get("resolved_events", []) or [])
    duplicate_ok = receipt.get("duplicate_prevented", firing <= 1)
    delivered = firing >= 1 and resolved >= 1 and duplicate_ok
    return {
        "status": "DELIVERED" if delivered else "INSUFFICIENT_EVIDENCE",
        "delivered": delivered,
        "firing_observed": firing >= 1,
        "resolution_observed": resolved >= 1,
        "duplicate_prevented": receipt.get("duplicate_prevented", True),
        "rule_name": receipt.get("rule_name", TEST_ALERT_RULE),
        "channel": receipt.get("channel", "internal_webhook"),
        "fired_at": receipt.get("fired_at"),
        "resolved_at": receipt.get("resolved_at"),
        "validated_at": datetime.now(UTC).isoformat(),
    }


def smtp_scope_decision(*, email_enabled: bool, smtp_configured: bool) -> dict[str, Any]:
    if email_enabled:
        return {
            "scope": "in_app_and_email",
            "smtp_required": True,
            "detail": "Email notifications advertised — SMTP validation required for GO",
            "customer_message": None,
        }
    return {
        "scope": "in_app_only",
        "smtp_required": False,
        "detail": "In-app notifications only for this deployment",
        "customer_message": (
            "Approval reminders and pilot communications are delivered in-app; "
            "email delivery is not enabled in this deployment."
        ),
    }


def compute_alert_notification_go_live_decision(evidence: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    insufficient: list[str] = []

    prom = evidence.get("prometheus_scrape_validation") or {}
    if not prom.get("scrape_healthy") or not prom.get("metrics_present"):
        insufficient.append("prometheus_scrape_not_confirmed")

    rules = evidence.get("alert_rule_load_validation") or {}
    if not rules.get("valid"):
        insufficient.append("alert_rules_not_loaded")

    alert = evidence.get("alert_delivery_validation") or {}
    if alert.get("status") != "DELIVERED":
        insufficient.append("alert_delivery_not_proven")

    scope = evidence.get("smtp_scope_decision") or {}
    smtp = evidence.get("smtp_validation") or {}
    if scope.get("smtp_required"):
        if smtp.get("status") != "DELIVERED":
            insufficient.append("smtp_delivery_not_proven")

    dep_after = evidence.get("deployment_readiness_after") or {}
    if dep_after.get("verdict") != "GO":
        if dep_after.get("verdict") == "NO_GO":
            blockers.append(f"deployment_readiness={dep_after.get('verdict')}")
        else:
            insufficient.append("deployment_readiness_not_go")

    ops = evidence.get("operations_readiness") or {}
    if ops.get("verdict") != "GO":
        blockers.append(f"operations_readiness={ops.get('verdict')}")

    redaction = evidence.get("redaction_scan") or {}
    if not redaction.get("passed"):
        blockers.append("redaction_scan_failed")

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
        "evaluated_at": datetime.now(UTC).isoformat(),
        "scoped_external_onboarding": verdict == "GO",
        "ga_ready": False,
    }


def write_alert_notification_artifacts(out_dir: Path, files: dict[str, dict]) -> dict[str, dict]:
    results = {}
    for name, payload in files.items():
        if payload is None:
            continue
        safe = redact_receiver_config(payload)
        results[name] = write_evidence_file(out_dir / name, safe)
    return results
