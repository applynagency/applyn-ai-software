"""Live operation preflight checks (Sprint 65G)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.integration_readiness.capabilities import block_reason_for_missing, check_capability


def preflight_live_operation(
    *,
    registry: dict,
    required_capabilities: list[str],
    environment_id: str | None,
    organization_id: str,
    idempotency_key: str,
    approval_satisfied: bool = True,
    explicit_simulation: bool = False,
) -> dict[str, Any]:
    if explicit_simulation:
        return {
            "allowed": True,
            "simulated": True,
            "reason": None,
            "remediation": None,
            "idempotency_key": idempotency_key,
        }
    state = registry.get("lifecycle_state", "DRAFT")
    mode = registry.get("provider_mode", "unavailable")
    caps = registry.get("capabilities") or {}

    if state not in ("CONNECTED", "DEGRADED"):
        return _blocked(
            f"Integration must be CONNECTED (current: {state})",
            "Validate the connection and resolve failures before retrying.",
            idempotency_key,
        )
    if mode != "live":
        return _blocked(
            f"Live execution requires provider mode 'live' (current: {mode})",
            "Enable and validate the integration with real credentials, or request explicit simulation.",
            idempotency_key,
        )
    if not registry.get("credential_id"):
        return _blocked("No credential reference configured", "Connect credentials via Secret Manager.", idempotency_key)
    if registry.get("reauth_required"):
        return _blocked("Reauthentication required", "Rotate or renew credentials and re-validate.", idempotency_key)
    if state == "EXPIRED":
        return _blocked("Credential expired", "Renew credentials before executing live operations.", idempotency_key)
    if not approval_satisfied:
        return _blocked("Approval policy not satisfied", "Complete approval workflow before execution.", idempotency_key)
    if registry.get("organization_id") and registry["organization_id"] != organization_id:
        return _blocked("Organization mismatch", "Connection does not belong to this organization.", idempotency_key)

    for cap in required_capabilities:
        if not check_capability(caps, cap):
            reason = block_reason_for_missing(caps, cap, mode)
            return _blocked(reason, f"Grant '{cap}' capability or use a connection with appropriate permissions.", idempotency_key)

    return {
        "allowed": True,
        "simulated": False,
        "reason": None,
        "remediation": None,
        "idempotency_key": idempotency_key,
        "environment_id": environment_id,
    }


def make_idempotency_key(*, org_id: str, operation: str, target_id: str) -> str:
    raw = json.dumps({"org": org_id, "op": operation, "target": target_id}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


def _blocked(reason: str, remediation: str, idempotency_key: str) -> dict[str, Any]:
    return {
        "allowed": False,
        "simulated": False,
        "reason": reason,
        "remediation": remediation,
        "idempotency_key": idempotency_key,
    }
