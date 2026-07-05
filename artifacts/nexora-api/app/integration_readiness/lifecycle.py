"""Integration connection lifecycle state machine (Sprint 65G)."""

from __future__ import annotations

from app.services.integration_verification import VStatus

VERIFICATION_TO_LIFECYCLE = {
    VStatus.CONNECTED: "CONNECTED",
    VStatus.PARTIAL: "DEGRADED",
    VStatus.FAILED: "FAILED",
    VStatus.UNAUTHORIZED: "REAUTH_REQUIRED",
    VStatus.TIMEOUT: "DEGRADED",
}

VERIFICATION_TO_MODE = {
    VStatus.CONNECTED: "live",
    VStatus.PARTIAL: "live",
    VStatus.FAILED: "unavailable",
    VStatus.UNAUTHORIZED: "unavailable",
    VStatus.TIMEOUT: "offline",
}


def map_verification_status(connection_status: str) -> tuple[str, str]:
    lifecycle = VERIFICATION_TO_LIFECYCLE.get(connection_status, "FAILED")
    mode = VERIFICATION_TO_MODE.get(connection_status, "unavailable")
    return lifecycle, mode


def should_transition_state(
    current: str, proposed: str, *, consecutive_failures: int, threshold: int = 3,
) -> str:
    if proposed == "CONNECTED":
        return "CONNECTED"
    if proposed in ("FAILED", "REAUTH_REQUIRED") and consecutive_failures < threshold:
        return current if current in ("CONNECTED", "DEGRADED") else proposed
    return proposed


def health_score_from_result(*, connected: bool, partial: bool, capabilities: dict) -> int:
    if not connected and not partial:
        return 0
    base = 60 if partial else 85
    granted = sum(1 for v in (capabilities or {}).values() if v)
    return min(100, base + min(granted * 3, 15))
