"""Progressive delivery rollout provider adapters (Sprint 65F)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

PROVIDER_TYPES = ("argo_rollouts", "flagger", "k8s_rolling", "gitops")


def detect_provider_mode(provider_type: str, *, configured: bool, secret: dict | None = None) -> str:
    if not configured:
        return "unavailable"
    if secret and secret.get("endpoint"):
        return "live"
    return "offline"


def propose_rollout(
    *,
    provider_type: str,
    strategy: str,
    target: str,
    steps: list[int] | None = None,
    mode: str = "offline",
) -> dict[str, Any]:
    steps = steps or [10, 25, 50, 100]
    return {
        "provider_type": provider_type,
        "strategy": strategy,
        "target": target,
        "mode": mode,
        "simulated": mode != "live",
        "traffic_steps": [{"weight": w, "at": datetime.now(UTC).isoformat()} for w in steps],
        "status": "PROPOSED",
        "revision": f"candidate-{datetime.now(UTC).strftime('%Y%m%d%H%M')}",
    }


def pause_rollout(state: dict) -> dict[str, Any]:
    return {**state, "status": "PAUSED", "paused_at": datetime.now(UTC).isoformat()}


def resume_rollout(state: dict) -> dict[str, Any]:
    return {**state, "status": "RUNNING", "resumed_at": datetime.now(UTC).isoformat()}


def promote_rollout(state: dict, *, weight: int = 100) -> dict[str, Any]:
    steps = list(state.get("traffic_steps", []))
    steps.append({"weight": weight, "at": datetime.now(UTC).isoformat(), "action": "promote"})
    return {**state, "status": "PROMOTED", "traffic_steps": steps, "current_weight": weight}


def abort_rollout(state: dict) -> dict[str, Any]:
    return {**state, "status": "ABORTED", "aborted_at": datetime.now(UTC).isoformat()}


def rollback_rollout(state: dict, *, target_revision: str | None = None) -> dict[str, Any]:
    history = list(state.get("revision_history", []))
    rev = target_revision or state.get("baseline_revision", "previous")
    history.append({"revision": rev, "at": datetime.now(UTC).isoformat(), "action": "rollback"})
    return {
        **state, "status": "ROLLED_BACK", "revision_history": history,
        "current_revision": rev, "simulated": state.get("mode") != "live",
    }


def inspect_rollout(state: dict) -> dict[str, Any]:
    return {
        "status": state.get("status", "UNKNOWN"),
        "current_weight": state.get("current_weight", 0),
        "traffic_steps": state.get("traffic_steps", []),
        "revision_history": state.get("revision_history", []),
        "simulated": state.get("simulated", True),
        "provider_mode": state.get("mode", "offline"),
    }
