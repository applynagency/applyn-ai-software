"""Executable pilot stage definitions (Sprint 66B)."""

from __future__ import annotations

PILOT_EXECUTION_STAGES: list[dict] = [
    {"key": "CONNECT", "title": "Connect integrations", "order": 1},
    {"key": "VALIDATE", "title": "Validate integration readiness", "order": 2},
    {"key": "READ_ONLY_ASSESSMENT", "title": "Run read-only assessment", "order": 3},
    {"key": "BASELINE_CAPTURE", "title": "Capture pilot baseline", "order": 4},
    {"key": "PROPOSE_OPERATION", "title": "Propose safe live operation", "order": 5},
    {"key": "CUSTOMER_APPROVAL", "title": "Obtain customer approval", "order": 6},
    {"key": "EXECUTE", "title": "Execute approved operation", "order": 7},
    {"key": "VERIFY", "title": "Verify post-operation health", "order": 8},
    {"key": "COMPLETE", "title": "Complete pilot", "order": 9},
]

PILOT_STAGE_KEYS: tuple[str, ...] = tuple(s["key"] for s in PILOT_EXECUTION_STAGES)

PILOT_EXECUTION_STATUSES = frozenset({
    "NOT_STARTED", "IN_PROGRESS", "BLOCKED", "FAILED", "COMPLETED",
})

STAGE_STATUSES = frozenset({"PENDING", "IN_PROGRESS", "COMPLETED", "BLOCKED", "FAILED"})

VERIFICATION_STATUSES = frozenset({
    "VERIFIED", "VERIFICATION_FAILED", "INSUFFICIENT_EVIDENCE", "PENDING",
})

SOURCE_MODES = frozenset({"LIVE", "SIMULATED", "OFFLINE", "UNAVAILABLE"})


def stage_index(stage_key: str) -> int:
    for i, s in enumerate(PILOT_EXECUTION_STAGES):
        if s["key"] == stage_key:
            return i
    raise KeyError(stage_key)


def next_stage_key(stage_key: str) -> str | None:
    idx = stage_index(stage_key)
    if idx + 1 >= len(PILOT_EXECUTION_STAGES):
        return None
    return PILOT_EXECUTION_STAGES[idx + 1]["key"]
