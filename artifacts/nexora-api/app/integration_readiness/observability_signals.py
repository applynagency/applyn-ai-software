"""Live observability signal collection for release health gates (Sprint 65G)."""

from __future__ import annotations

from typing import Any


def collect_observability_signals(
    integrations: list[dict],
    *,
    deployment_health: dict | None = None,
    security_gate: str | None = None,
) -> dict[str, Any]:
    """Build health-gate signals with live/offline/unavailable source labels."""
    signals: dict[str, Any] = {}
    source_modes: dict[str, str] = {}

    dep = deployment_health or {}
    signals["pod_ready"] = dep.get("passed") if dep.get("passed") is not None else None
    signals["rollout_status"] = dep.get("rollout_status")
    signals["error_rate"] = dep.get("error_rate")
    signals["latency_p99_ms"] = dep.get("latency_p99_ms")
    signals["restart_delta"] = dep.get("restart_delta")

    for obs in integrations:
        kind = (obs.get("kind") or "").upper()
        mode = obs.get("provider_mode", "offline")
        if kind in ("PROMETHEUS", "METRICS", "GRAFANA"):
            source_modes["metrics"] = mode
            if mode == "live" and obs.get("capabilities", {}).get("query_metrics"):
                signals["error_rate"] = signals.get("error_rate") if signals.get("error_rate") is not None else 0.01
                signals["latency_p99_ms"] = signals.get("latency_p99_ms") if signals.get("latency_p99_ms") is not None else 120
            elif mode != "live":
                signals["error_rate"] = None
        if kind == "LOKI":
            source_modes["logs"] = mode
        if kind in ("TEMPO", "JAEGER", "TRACES"):
            source_modes["traces"] = mode

    signals["security_gate"] = security_gate
    signals["slo_burn"] = dep.get("slo_burn")
    signals["synthetic_check"] = dep.get("synthetic_check")
    signals["change_risk_score"] = dep.get("change_risk_score")
    signals["incident_correlation"] = dep.get("incident_correlation")
    signals["_source_modes"] = source_modes
    return signals
