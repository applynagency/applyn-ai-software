"""Sprint 67F — Staging go-live evidence tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from app.pilot.monitoring_rules import validate_customer_pilot_alert_rules
from app.pilot.staging_evidence import (
    EXPECTED_HEAD,
    compute_go_live_decision,
    redact_evidence_blob,
    safe_evidence_dict,
    write_evidence_file,
)


def test_go_live_decision_no_go_on_debug():
    evidence = {
        "configuration_validation": {"debug_enabled": True, "pilot_mode_enabled": True, "pilot_mode_all_orgs": False},
        "migration_state": {"current": EXPECTED_HEAD, "head": EXPECTED_HEAD, "head_count": 1},
        "operations_readiness": {"verdict": "GO"},
        "deployment_readiness": {"verdict": "INSUFFICIENT_EVIDENCE"},
        "scheduler_reminder_validation": {"scheduler_lock_acquired": True, "duplicate_prevented": True},
        "smtp_validation": {"status": "NOT_CONFIGURED"},
        "prometheus_scrape_validation": {"metrics_present": True},
        "alert_delivery_validation": {"status": "INSUFFICIENT_EVIDENCE"},
        "backup_restore_validation": {"valid": True},
        "portal_dry_run": {"passed": True},
        "runbook_walkthrough": {"completed": True},
    }
    decision = compute_go_live_decision(evidence)
    assert decision["verdict"] == "NO_GO"
    assert decision["ga_ready"] is False


def test_go_live_decision_insufficient_without_alert():
    evidence = {
        "configuration_validation": {"debug_enabled": False, "pilot_mode_enabled": True, "pilot_mode_all_orgs": False},
        "migration_state": {"current": EXPECTED_HEAD, "head": EXPECTED_HEAD, "head_count": 1},
        "operations_readiness": {"verdict": "GO"},
        "deployment_readiness": {"verdict": "INSUFFICIENT_EVIDENCE"},
        "scheduler_reminder_validation": {"scheduler_lock_acquired": True, "duplicate_prevented": True},
        "smtp_validation": {"status": "NOT_CONFIGURED"},
        "prometheus_scrape_validation": {"metrics_present": False},
        "alert_delivery_validation": {"status": "INSUFFICIENT_EVIDENCE"},
        "backup_restore_validation": {"valid": True},
        "portal_dry_run": {"passed": True},
        "runbook_walkthrough": {"completed": True},
    }
    decision = compute_go_live_decision(evidence)
    assert decision["verdict"] == "INSUFFICIENT_EVIDENCE"


def test_redact_evidence_removes_connection_strings():
    blob = redact_evidence_blob('{"url":"postgresql://user:pass@host/db"}')
    assert "postgresql://" not in blob


def test_safe_evidence_dict_strips_tokens():
    safe = safe_evidence_dict({"confirmation_token": "abc", "title": "ok"})
    assert "confirmation_token" not in safe


def test_write_evidence_file_blocks_secrets(tmp_path):
    bad = write_evidence_file(tmp_path / "bad.json", {"password": "supersecret"})
    assert bad["written"] is False


def test_write_evidence_file_ok(tmp_path):
    ok = write_evidence_file(tmp_path / "ok.json", {"verdict": "INSUFFICIENT_EVIDENCE"})
    assert ok["written"] is True
    data = json.loads((tmp_path / "ok.json").read_text())
    assert data["verdict"] == "INSUFFICIENT_EVIDENCE"


def test_alert_rules_staging_file():
    result = validate_customer_pilot_alert_rules()
    assert result["valid"] is True


@pytest.mark.asyncio
async def test_staging_validation_script_importable():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "scripts" / "pilot_sprint67f_staging_validation.py"
    spec = importlib.util.spec_from_file_location("pilot_sprint67f", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    cfg = await mod._configuration_validation()
    assert "migration_head" in cfg
