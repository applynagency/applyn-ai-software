"""Sprint 67G — Alerting and notification go-live validation tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.pilot.alert_notification_evidence import (
    compute_alert_notification_go_live_decision,
    parse_receiver_receipts,
    redact_receiver_config,
    smtp_scope_decision,
    validate_alert_delivery_evidence,
)
from app.pilot.deployment_readiness import evaluate_pilot_deployment_readiness
from app.pilot.monitoring_rules import REQUIRED_PROMETHEUS_METRICS, validate_customer_pilot_alert_rules
from app.pilot.staging_evidence import write_evidence_file
from app.tests.test_customer_pilot_deployment import _deploy_payload, _ops_payload


def test_alert_rules_include_deployment_unhealthy():
    result = validate_customer_pilot_alert_rules()
    assert result["valid"] is True
    assert "CustomerPilotDeploymentUnhealthy" in result["alerts_found"]


def test_required_prometheus_metrics_list():
    assert "nexora_customer_pilot_deployment_healthy" in REQUIRED_PROMETHEUS_METRICS


def test_smtp_scope_in_app_only():
    scope = smtp_scope_decision(email_enabled=False, smtp_configured=False)
    assert scope["scope"] == "in_app_only"
    assert scope["smtp_required"] is False
    assert "in-app" in scope["customer_message"].lower()


def test_smtp_scope_email_mode_requires_smtp():
    scope = smtp_scope_decision(email_enabled=True, smtp_configured=False)
    assert scope["smtp_required"] is True


def test_deployment_readiness_in_app_only_smtp_not_insufficient():
    result = evaluate_pilot_deployment_readiness(_deploy_payload(
        email_notifications_enabled=False,
        alert_receiver_configured=True,
        alert_delivery_verified=True,
    ))
    assert "smtp_not_configured" not in result["insufficient_evidence"]
    smtp_check = next(c for c in result["checks"] if c["name"] == "smtp_delivery")
    assert smtp_check["passed"] is True
    assert result["notification_scope"] == "in_app_only"


def test_deployment_readiness_alert_delivery_required_for_go():
    result = evaluate_pilot_deployment_readiness(_deploy_payload(
        email_notifications_enabled=False,
        alert_receiver_configured=False,
    ))
    assert result["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert "alert_receiver_not_configured" in result["insufficient_evidence"]


def test_deployment_readiness_go_with_alert_and_in_app_only():
    result = evaluate_pilot_deployment_readiness(_deploy_payload(
        email_notifications_enabled=False,
        alert_receiver_configured=True,
        alert_delivery_verified=True,
    ))
    assert result["verdict"] == "GO"


def test_deployment_readiness_smtp_required_when_email_enabled():
    result = evaluate_pilot_deployment_readiness(_deploy_payload(
        email_notifications_enabled=True,
        smtp_configured=False,
        alert_receiver_configured=True,
        alert_delivery_verified=True,
    ))
    assert result["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert "smtp_not_configured" in result["insufficient_evidence"]


def test_alert_delivery_evidence_delivered():
    receipt = {
        "firing_count": 1,
        "resolved_count": 1,
        "duplicate_prevented": True,
        "fired_at": "2026-07-02T00:00:00+00:00",
        "resolved_at": "2026-07-02T00:05:00+00:00",
    }
    result = validate_alert_delivery_evidence(receipt)
    assert result["status"] == "DELIVERED"
    assert result["delivered"] is True


def test_alert_delivery_evidence_insufficient_without_resolution():
    result = validate_alert_delivery_evidence({"firing_count": 1, "resolved_count": 0})
    assert result["status"] == "INSUFFICIENT_EVIDENCE"


def test_redact_receiver_config_hides_webhook():
    redacted = redact_receiver_config({
        "webhook_url": "http://secret-receiver/webhook",
        "channel": "internal",
    })
    assert redacted["webhook_url"] == "[REDACTED]"


def test_go_live_decision_go_when_all_evidence_present():
    evidence = {
        "prometheus_scrape_validation": {"scrape_healthy": True, "metrics_present": True},
        "alert_rule_load_validation": {"valid": True},
        "alert_delivery_validation": {"status": "DELIVERED"},
        "smtp_scope_decision": {"smtp_required": False},
        "deployment_readiness_after": {"verdict": "GO"},
        "operations_readiness": {"verdict": "GO"},
        "redaction_scan": {"passed": True},
    }
    decision = compute_alert_notification_go_live_decision(evidence)
    assert decision["verdict"] == "GO"


def test_go_live_decision_insufficient_without_alert():
    evidence = {
        "prometheus_scrape_validation": {"scrape_healthy": True, "metrics_present": True},
        "alert_rule_load_validation": {"valid": True},
        "alert_delivery_validation": {"status": "INSUFFICIENT_EVIDENCE"},
        "smtp_scope_decision": {"smtp_required": False},
        "deployment_readiness_after": {"verdict": "INSUFFICIENT_EVIDENCE"},
        "operations_readiness": {"verdict": "GO"},
        "redaction_scan": {"passed": True},
    }
    decision = compute_alert_notification_go_live_decision(evidence)
    assert decision["verdict"] == "INSUFFICIENT_EVIDENCE"


def test_write_evidence_blocks_password_key(tmp_path: Path):
    bad = write_evidence_file(tmp_path / "bad.json", {"password": "supersecret"})
    assert bad["written"] is False


def test_parse_receiver_receipts_missing_file(tmp_path: Path):
    result = parse_receiver_receipts(tmp_path / "missing.json")
    assert result["delivered"] is False


@pytest.mark.asyncio
async def test_alert_test_signal_endpoint_disabled(client):
    from app.tests.test_customer_pilot_portal import _headers_org

    headers, _ = await _headers_org(client, email="alert-tst@e.com", username="alerttst", slug="alert-tst")
    resp = await client.post("/v1/pilot/internal/alert-test-signal", headers=headers, params={"value": 1})
    assert resp.status_code in (403, 422)


@pytest.mark.asyncio
async def test_deployment_readiness_output_has_no_secrets(client):
    from app.tests.test_customer_pilot_portal import _headers_org

    headers, _ = await _headers_org(client, email="sec-dep@e.com", username="secdep", slug="sec-dep")
    resp = await client.get("/v1/pilot/deployment-readiness", headers=headers)
    assert resp.status_code == 200
    blob = resp.text.lower()
    assert "postgresql://" not in blob
    assert "webhook" not in blob or "insufficient" in blob
