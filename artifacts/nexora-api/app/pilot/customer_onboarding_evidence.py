"""Sprint 68A — First customer non-production pilot onboarding evidence helpers."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.pilot.customer_portal import assert_export_safe
from app.pilot.staging_evidence import redact_evidence_blob

_SECRET_PATTERNS = (
    re.compile(r"(?i)(token|password|secret|api[_-]?key)\s*[:=]\s*\S+"),
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"kubeconfig", re.I),
    re.compile(r"postgresql://"),
)


def redact_onboarding_blob(data: Any) -> Any:
    if isinstance(data, dict):
        blocked_keys = {"secret", "kubeconfig", "token", "password", "credentials"}
        return {
            k: "[REDACTED]" if k.lower() in blocked_keys else redact_onboarding_blob(v)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [redact_onboarding_blob(v) for v in data]
    if isinstance(data, str):
        out = redact_evidence_blob(data)
        for pat in _SECRET_PATTERNS:
            out = pat.sub("[REDACTED]", out)
        return out
    return data


def compute_onboarding_status(evidence: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    insufficient: list[str] = []

    gates = {
        "integration_readiness": evidence.get("integration_readiness", {}).get("verdict"),
        "launch_readiness": evidence.get("launch_readiness", {}).get("verdict"),
        "operations_readiness": evidence.get("operations_readiness", {}).get("verdict"),
        "deployment_readiness": evidence.get("deployment_readiness", {}).get("verdict"),
    }
    for name, verdict in gates.items():
        if verdict != "GO":
            if verdict in (None, "ERROR"):
                insufficient.append(f"{name}_missing")
            elif verdict == "INSUFFICIENT_EVIDENCE":
                insufficient.append(name)
            else:
                blockers.append(f"{name}={verdict}")

    providers = evidence.get("provider_onboarding") or {}
    for provider in ("KUBERNETES", "GITEA", "PROMETHEUS"):
        row = providers.get(provider) or {}
        if row.get("lifecycle") != "CONNECTED" or row.get("provider_mode") != "live":
            insufficient.append(f"provider_{provider.lower()}_not_ready")

    baseline = evidence.get("baseline_capture") or {}
    assessment = evidence.get("assessment") or {}
    if not assessment.get("completed"):
        insufficient.append("assessment_incomplete")
    if not baseline.get("completed"):
        insufficient.append("baseline_incomplete")

    if evidence.get("provider_mutation"):
        blockers.append("provider_mutation_detected")

    redaction = evidence.get("redaction_scan") or {}
    if not redaction.get("passed"):
        blockers.append("redaction_scan_failed")

    if blockers:
        status = "STOP"
        recommendation = "STOP — remediation required before customer approval package"
    elif insufficient:
        status = "STOP"
        recommendation = "STOP — insufficient evidence; complete onboarding gates"
    elif evidence.get("operation_proposal_created"):
        recommendation = "READY FOR OPERATOR EXECUTION — separate explicit authorization required"
        status = "READY_FOR_OPERATOR_EXECUTION"
    else:
        status = "READY_FOR_CUSTOMER_APPROVAL_PACKAGE"
        recommendation = (
            "READY FOR CUSTOMER APPROVAL PACKAGE — customer may review assessment; "
            "no operation proposed or executed in this sprint"
        )

    return {
        "status": status,
        "recommendation": recommendation,
        "blockers": blockers,
        "insufficient_evidence": insufficient,
        "readiness_gates": gates,
        "provider_mutation": bool(evidence.get("provider_mutation")),
        "execution_performed": bool(evidence.get("execution_performed")),
        "evaluated_at": datetime.now(UTC).isoformat(),
        "ga_ready": False,
    }


def write_onboarding_artifact(path, payload: dict) -> dict:
    """Write customer-safe onboarding JSON without whole-blob truncation."""
    redacted = redact_onboarding_blob(payload)
    try:
        assert_export_safe(redacted)
    except Exception as exc:
        return {"written": False, "path": str(path), "error": str(exc)}
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(redacted, indent=2, default=str), encoding="utf-8")
    return {"written": True, "path": str(path)}
