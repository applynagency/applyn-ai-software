"""Customer-safe pilot portal helpers (Sprint 67B)."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any

from app.integration_readiness.evidence import redact_text

_INTERNAL_PATTERNS = (
    re.compile(r"41a17fb0", re.I),
    re.compile(r"nexora-pilot", re.I),
    re.compile(r"pilot-demo", re.I),
    re.compile(r"INTERNAL_NON_PRODUCTION", re.I),
    re.compile(r"gitea", re.I),
    re.compile(r"k3s", re.I),
)

_SECRET_PATTERNS = (
    re.compile(r"(?i)(token|password|secret|api[_-]?key)\s*[:=]\s*\S+"),
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"-----BEGIN"),
)

ACTIVE_OPERATION_STATUSES = frozenset({
    "PENDING_CONFIRMATION",
    "AWAITING_APPROVAL",
    "EXECUTING",
    "PENDING_VERIFICATION",
})


def operator_execution_console_label(
    operation_status: str,
    approval_status: str | None = None,
    *,
    ready_for_typed_confirmation: bool = False,
) -> str:
    """Operator-facing state label for the execution console list/detail."""
    op = (operation_status or "").upper()
    ap = (approval_status or "").upper()
    if ap in ("REJECTED", "INVALIDATED", "EXPIRED") or op in ("CANCELLED", "FAILED"):
        return "Blocked"
    if op == "AWAITING_APPROVAL" or ap == "PENDING":
        return "Waiting for customer approval"
    if ready_for_typed_confirmation or (ap == "APPROVED" and op == "PENDING_CONFIRMATION"):
        return "Ready for typed confirmation"
    if op == "SUCCEEDED" or op == "PENDING_VERIFICATION":
        return op.replace("_", " ").title()
    return op.replace("_", " ").title() or "Unknown"


def rollback_plan_hash(plan: str | None) -> str:
    return hashlib.sha256((plan or "").encode()).hexdigest()[:64]


def sanitize_customer_view(data: Any) -> Any:
    """Remove internal identifiers and redact sensitive strings."""
    if isinstance(data, dict):
        out = {}
        for k, v in data.items():
            if k in ("confirmation_token", "kubeconfig", "secret", "token"):
                continue
            out[k] = sanitize_customer_view(v)
        return out
    if isinstance(data, list):
        return [sanitize_customer_view(v) for v in data]
    if isinstance(data, str):
        text = redact_text(data)
        for pat in _INTERNAL_PATTERNS:
            text = pat.sub("[REDACTED]", text)
        return text
    return data


def scan_for_secrets(blob: str) -> list[str]:
    hits: list[str] = []
    for pat in _SECRET_PATTERNS:
        if pat.search(blob):
            hits.append(pat.pattern[:40])
    return hits


def assert_export_safe(pack: dict) -> None:
    blob = json.dumps(pack, default=str)
    hits = scan_for_secrets(blob)
    if hits:
        from app.core.exceptions import ValidationError
        raise ValidationError("Export blocked — potential secrets detected in evidence pack")


def operator_handoff_label(blockers: list[str], gates: dict) -> str:
    if any("INSUFFICIENT" in b.upper() for b in blockers):
        return "INSUFFICIENT_EVIDENCE"
    if blockers:
        return "BLOCKED"
    if gates.get("ready_for_typed_confirmation"):
        return "READY"
    return "BLOCKED"


def customer_timeline_entry(*, stage_key: str, status: str, outcome: str | None = None) -> dict:
    return {
        "stage_key": stage_key,
        "status": status,
        "outcome": outcome,
        "customer_label": stage_key.replace("_", " ").title(),
    }


def notification_payload(*, title: str, summary: str, path: str, event_type: str) -> dict:
    return {
        "title": title,
        "summary": summary,
        "url": path,
        "action_url": path,
        "priority": "normal",
        "category": "customer_pilot",
        "event_type": event_type,
        "generated_at": datetime.now(UTC).isoformat(),
    }
