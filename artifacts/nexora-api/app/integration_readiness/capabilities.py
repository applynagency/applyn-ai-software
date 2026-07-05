"""Capability-based authorization for integrations (Sprint 65G)."""

from __future__ import annotations

from typing import Any

WRITE_CAPABILITIES = frozenset({
    "deploy", "promote", "rollback", "scale", "sync", "write", "exec",
    "traffic_shift", "apply", "mutate",
})

K8S_WRITE_CAPS = frozenset({"rollout", "scale", "apply", "patch", "create", "update", "delete"})
K8S_READ_ONLY_INDICATORS = frozenset({"read_only", "readonly", "get", "list", "watch"})


def build_capability_matrix(provider_type: str, permissions: list[str]) -> dict[str, bool]:
    perms = {p.lower() for p in permissions}
    matrix: dict[str, bool] = {
        "read": bool(perms) or provider_type in ("OFFLINE",),
        "write": False,
        "deploy": False,
        "apply": False,
        "query_metrics": False,
        "query_logs": False,
        "query_traces": False,
        "traffic_shift": False,
        "sync_gitops": False,
    }
    for p in perms:
        if any(w in p for w in WRITE_CAPABILITIES):
            matrix["write"] = True
            matrix["deploy"] = True
        if "apply" in p or "terraform" in p or "iac" in p:
            matrix["apply"] = True
        if "metric" in p or "prometheus" in p or "query" in p:
            matrix["query_metrics"] = True
        if "log" in p or "loki" in p:
            matrix["query_logs"] = True
        if "trace" in p or "tempo" in p or "jaeger" in p:
            matrix["query_traces"] = True
        if "sync" in p or "argocd" in p or "flux" in p:
            matrix["sync_gitops"] = True
        if "rollout" in p or "canary" in p or "traffic" in p:
            matrix["traffic_shift"] = True
    if provider_type.upper() in ("KUBERNETES", "K8S"):
        has_write_cap = any(
            any(cap in p for cap in K8S_WRITE_CAPS) for p in perms
        )
        read_only_only = bool(perms) and all(
            any(r in p for r in K8S_READ_ONLY_INDICATORS) for p in perms
        )
        matrix["write"] = has_write_cap and not read_only_only
        # Namespace-scoped scale RBAC does not grant delivery/deploy semantics.
        if matrix["write"] and not any(p.startswith("deploy:") for p in perms):
            matrix["deploy"] = False
    return matrix


def check_capability(capabilities: dict, required: str) -> bool:
    return bool((capabilities or {}).get(required))


def block_reason_for_missing(capabilities: dict, required: str, provider_mode: str) -> str:
    if provider_mode != "live":
        return f"Provider mode is {provider_mode}; live capability '{required}' not available"
    if not check_capability(capabilities, required):
        return f"Validated capability '{required}' is not granted for this connection"
    return ""


def enforce_write_allowed(capabilities: dict, *, provider_mode: str, lifecycle_state: str) -> dict[str, Any]:
    if lifecycle_state not in ("CONNECTED", "DEGRADED"):
        return {"allowed": False, "reason": f"Integration state is {lifecycle_state}"}
    if provider_mode != "live":
        return {"allowed": False, "reason": "Write operations require live provider mode"}
    if not check_capability(capabilities, "write"):
        return {"allowed": False, "reason": "Connection is read-only; write operations blocked"}
    return {"allowed": True, "reason": None}
