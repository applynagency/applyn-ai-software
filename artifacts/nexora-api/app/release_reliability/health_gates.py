"""Health gate evaluation for release verification (Sprint 65F)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

GATE_PASS = "PASS"
GATE_WARN = "WARN"
GATE_FAIL = "FAIL"
GATE_INSUFFICIENT = "INSUFFICIENT_EVIDENCE"

DEFAULT_THRESHOLDS = {
    "error_rate_max": 0.05,
    "latency_p99_ms_max": 2000,
    "restart_delta_max": 3,
    "slo_burn_max": 0.25,
    "security_gate_required": True,
}


def evaluate_health_gate(
    signals: dict[str, Any],
    *,
    thresholds: dict | None = None,
    environment_tier: str = "STAGING",
    is_production: bool = False,
) -> dict[str, Any]:
    """Evaluate health gate from observability/control-plane signals. Never fabricates PASS."""
    thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    evaluated: dict[str, Any] = {}
    evidence_refs: list[dict] = []
    insufficient_signals: list[str] = []
    failures: list[str] = []
    warnings: list[str] = []

    def _check(name: str, value: Any, *, required: bool = False) -> None:
        evaluated[name] = value
        if value is None:
            if required:
                insufficient_signals.append(name)
            return
        evidence_refs.append({"signal": name, "value": value, "at": datetime.now(UTC).isoformat()})

    _check("pod_ready", signals.get("pod_ready"), required=True)
    _check("rollout_status", signals.get("rollout_status"), required=True)
    _check("error_rate", signals.get("error_rate"))
    _check("latency_p99_ms", signals.get("latency_p99_ms"))
    _check("restart_delta", signals.get("restart_delta"))
    _check("slo_burn", signals.get("slo_burn"))
    _check("synthetic_check", signals.get("synthetic_check"))
    _check("security_gate", signals.get("security_gate"))
    _check("change_risk_score", signals.get("change_risk_score"))
    _check("incident_correlation", signals.get("incident_correlation"))

    if signals.get("pod_ready") is False:
        failures.append("pods_not_ready")
    if signals.get("rollout_status") not in (None, "Complete", "Healthy", "Succeeded"):
        if signals.get("rollout_status"):
            failures.append("rollout_incomplete")

    err = signals.get("error_rate")
    if err is not None and err > thresholds["error_rate_max"]:
        failures.append("error_rate_exceeded")

    lat = signals.get("latency_p99_ms")
    if lat is not None and lat > thresholds["latency_p99_ms_max"]:
        warnings.append("latency_elevated")

    restarts = signals.get("restart_delta")
    if restarts is not None and restarts > thresholds["restart_delta_max"]:
        failures.append("restart_spike")

    burn = signals.get("slo_burn")
    if burn is not None and burn > thresholds["slo_burn_max"]:
        failures.append("slo_burn_exceeded")

    sec = signals.get("security_gate")
    if thresholds.get("security_gate_required") and sec in (None, "BLOCK", "FAIL"):
        if sec is None:
            insufficient_signals.append("security_gate")
        else:
            failures.append("security_gate_blocked")

    source_modes = signals.get("_source_modes") or {}
    if is_production:
        for required_source in ("metrics", "logs"):
            mode = source_modes.get(required_source)
            if mode in (None, "unavailable", "offline"):
                insufficient_signals.append(f"live_{required_source}")

    if failures:
        decision = GATE_FAIL
    elif warnings:
        decision = GATE_WARN
    elif insufficient_signals:
        decision = GATE_INSUFFICIENT
    elif signals.get("pod_ready") is True and signals.get("rollout_status"):
        decision = GATE_PASS
    else:
        decision = GATE_INSUFFICIENT

    if is_production and decision == GATE_INSUFFICIENT:
        decision = GATE_INSUFFICIENT

    if is_production and decision == GATE_WARN:
        decision = GATE_FAIL

    return {
        "decision": decision,
        "signals": evaluated,
        "thresholds": thresholds,
        "evidence_refs": evidence_refs,
        "failures": failures,
        "warnings": warnings,
        "insufficient_signals": insufficient_signals,
        "evaluated_at": datetime.now(UTC).isoformat(),
        "blocks_promotion": decision in (GATE_FAIL, GATE_INSUFFICIENT) and is_production,
    }
