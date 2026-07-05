"""Provider-specific validation probes (Sprint 65G)."""

from __future__ import annotations

import shutil
from typing import Any

from app.infrastructure.validator import InfrastructureValidator
from app.services.integration_verification import VStatus, verify_provider

_validator = InfrastructureValidator()


async def probe_marketplace_connection(integration_key: str, secret: dict) -> dict[str, Any]:
    result = await verify_provider(integration_key, secret)
    return result.to_dict()


async def probe_kubernetes(secret: dict) -> dict[str, Any]:
    report = _validator.validate("KUBERNETES", secret)
    checks = report.as_dict()
    status = VStatus.CONNECTED if report.verified else VStatus.PARTIAL if report.passed_count else VStatus.FAILED
    permissions = [c["name"] for c in checks.get("checks", []) if c.get("passed")]
    return {
        "connection_status": status,
        "permissions": permissions,
        "capabilities_hint": {
            "write": any("deploy" in p.lower() or "scale" in p.lower() for p in permissions),
            "read_only": not any("write" in p.lower() for p in permissions),
        },
        "provider_identity": {"provider": "KUBERNETES"},
        "errors": [] if report.verified else [report.guidance[:200]],
        "warnings": [],
    }


def probe_security_binary(provider_type: str) -> dict[str, Any]:
    binaries = {"TRIVY": "trivy", "GITLEAKS": "gitleaks", "SEMGREP": "semgrep", "CHECKOV": "checkov"}
    binary = binaries.get(provider_type.upper())
    if not binary:
        return {"connection_status": VStatus.FAILED, "permissions": [], "errors": ["unsupported provider"]}
    if shutil.which(binary):
        return {"connection_status": VStatus.CONNECTED, "permissions": ["scan"], "provider_mode": "live"}
    return {"connection_status": VStatus.TIMEOUT, "permissions": [], "provider_mode": "offline", "warnings": ["binary not on PATH"]}


def probe_observability(kind: str, config: dict) -> dict[str, Any]:
    endpoint = (config or {}).get("endpoint") or (config or {}).get("url")
    if not endpoint:
        return {
            "connection_status": VStatus.TIMEOUT,
            "permissions": [],
            "provider_mode": "offline",
            "warnings": ["no endpoint configured"],
        }
    cap = "query_metrics" if kind.upper() in ("PROMETHEUS", "METRICS") else "query_logs" if kind.upper() == "LOKI" else "query_traces"
    return {
        "connection_status": VStatus.CONNECTED,
        "permissions": [cap],
        "provider_mode": "live",
        "provider_identity": {"endpoint": endpoint.split("?")[0][:120]},
    }


def probe_notification(channel: str, config: dict) -> dict[str, Any]:
    if not (config or {}).get("webhook_url") and not (config or {}).get("smtp_host"):
        return {"connection_status": VStatus.FAILED, "permissions": [], "errors": ["no webhook or SMTP configured"]}
    return {"connection_status": VStatus.CONNECTED, "permissions": ["notify"], "provider_mode": "live"}
