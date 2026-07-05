"""Environment promotion policies and queue (Sprint 65F)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

PROMOTION_CHAIN = [
    ("DEVELOPMENT", "QA"),
    ("QA", "UAT"),
    ("UAT", "STAGING"),
    ("STAGING", "PRODUCTION"),
]

DEFAULT_POLICIES = [
    {"source_tier": s, "target_tier": t, "requires_verification": True,
     "requires_security_gate": t == "PRODUCTION", "requires_approval": t in ("STAGING", "PRODUCTION"),
     "digest_immutable": True, "enabled": True}
    for s, t in PROMOTION_CHAIN
]


def evaluate_promotion(
    *,
    source_verification: str,
    security_gate: str | None,
    artifact_digest: str,
    existing_digest: str | None,
    policy: dict,
    freeze_active: bool,
    environment_tier: str,
) -> dict[str, Any]:
    blocks: list[str] = []
    if freeze_active:
        blocks.append("freeze_window_active")
    if policy.get("requires_verification") and source_verification not in ("PASSED", "PASS"):
        if source_verification == "INSUFFICIENT_EVIDENCE" and environment_tier == "PRODUCTION":
            blocks.append("insufficient_verification_evidence")
        elif source_verification not in ("PASSED", "PASS", "WARN"):
            blocks.append("verification_not_passed")
    if policy.get("requires_security_gate") and security_gate in (None, "BLOCK", "FAIL"):
        blocks.append("security_gate_blocked")
    if policy.get("digest_immutable") and existing_digest and existing_digest != artifact_digest:
        blocks.append("artifact_digest_mismatch")
    return {
        "allowed": not blocks,
        "block_reasons": blocks,
        "requires_approval": policy.get("requires_approval", True),
    }


def is_freeze_active(windows: list[dict], *, tier: str | None, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    for w in windows:
        if not w.get("active", True):
            continue
        if w.get("environment_tier") and tier and w["environment_tier"] != tier:
            continue
        starts = w.get("starts_at")
        ends = w.get("ends_at")
        if starts and ends:
            if getattr(starts, "tzinfo", None) is None:
                starts = starts.replace(tzinfo=UTC)
            if getattr(ends, "tzinfo", None) is None:
                ends = ends.replace(tzinfo=UTC)
            if starts <= now <= ends:
                return True
    return False
