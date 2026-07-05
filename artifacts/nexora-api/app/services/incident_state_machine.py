"""Sprint 58A.4 — Incident lifecycle state machine.

A small, dependency-free module that defines the validated transition graph for
``IncidentLifecycleStatus`` and the timestamp/assignment-state side effects of
each state. Kept separate so it is trivially unit-testable.
"""

from __future__ import annotations

from app.models.incident import IncidentLifecycleStatus as S
from app.models.oncall import IncidentAssignmentState

# Allowed transitions. CLOSED and RESOLVED can be re-opened to INVESTIGATING.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    S.OPEN.value: {S.ACKNOWLEDGED.value, S.INVESTIGATING.value, S.ESCALATED.value, S.CLOSED.value},
    S.ACKNOWLEDGED.value: {
        S.INVESTIGATING.value, S.MITIGATING.value, S.ESCALATED.value,
        S.RESOLVED.value, S.CLOSED.value,
    },
    S.INVESTIGATING.value: {
        S.ACKNOWLEDGED.value, S.MITIGATING.value, S.ESCALATED.value,
        S.RESOLVED.value, S.CLOSED.value,
    },
    S.MITIGATING.value: {
        S.INVESTIGATING.value, S.ESCALATED.value, S.RESOLVED.value, S.CLOSED.value,
    },
    S.ESCALATED.value: {
        S.ACKNOWLEDGED.value, S.INVESTIGATING.value, S.MITIGATING.value,
        S.RESOLVED.value, S.CLOSED.value,
    },
    S.RESOLVED.value: {S.CLOSED.value, S.INVESTIGATING.value},
    S.CLOSED.value: {S.INVESTIGATING.value},
}

# A lifecycle state's equivalent on-call assignment state, when one exists, so
# the two stay reconciled (assignment only models OPEN/ACK/INVESTIGATING/RESOLVED).
LIFECYCLE_TO_ASSIGNMENT: dict[str, str] = {
    S.OPEN.value: IncidentAssignmentState.OPEN.value,
    S.ACKNOWLEDGED.value: IncidentAssignmentState.ACKNOWLEDGED.value,
    S.INVESTIGATING.value: IncidentAssignmentState.INVESTIGATING.value,
    S.MITIGATING.value: IncidentAssignmentState.INVESTIGATING.value,
    S.ESCALATED.value: IncidentAssignmentState.INVESTIGATING.value,
    S.RESOLVED.value: IncidentAssignmentState.RESOLVED.value,
    S.CLOSED.value: IncidentAssignmentState.RESOLVED.value,
}

TERMINAL_STATES = {S.CLOSED.value}
VALID_STATES = {s.value for s in S}


def normalize(status: str | None) -> str:
    return (status or "").strip().upper()


def is_valid_state(status: str | None) -> bool:
    return normalize(status) in VALID_STATES


def can_transition(from_status: str, to_status: str) -> bool:
    return normalize(to_status) in ALLOWED_TRANSITIONS.get(normalize(from_status), set())


def assignment_state_for(lifecycle_status: str) -> str | None:
    return LIFECYCLE_TO_ASSIGNMENT.get(normalize(lifecycle_status))
