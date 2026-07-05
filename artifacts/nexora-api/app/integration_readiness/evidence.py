"""Redacted evidence collection for live operations (Sprint 65G)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

_MAX_EVIDENCE_BYTES = 32_768
_SECRET_RE = re.compile(
    r"(?ix)"
    r"("
    r"(?:token|password|secret|api[_-]?key)\s*[:=]\s*\S+"
    r"|bearer\s+\S+"
    r")"
)


def redact_text(text: str, *, max_bytes: int = _MAX_EVIDENCE_BYTES) -> str:
    if not text:
        return ""
    redacted = _SECRET_RE.sub("[REDACTED]", text)
    if len(redacted.encode()) > max_bytes:
        return redacted.encode()[:max_bytes].decode("utf-8", errors="ignore") + "\n...[truncated]"
    return redacted


def build_live_evidence(
    *,
    correlation_id: str | None,
    resource_ids: dict | None,
    outcome: str,
    pre_state: dict | None = None,
    post_state: dict | None = None,
    log_snippet: str | None = None,
    observability_refs: list | None = None,
) -> dict[str, Any]:
    return {
        "correlation_id": correlation_id,
        "resource_ids": resource_ids or {},
        "timestamps": {"recorded_at": datetime.now(UTC).isoformat()},
        "outcome": outcome,
        "pre_state": pre_state or {},
        "post_state": post_state or {},
        "logs_redacted": redact_text(log_snippet or ""),
        "observability_refs": observability_refs or [],
    }
