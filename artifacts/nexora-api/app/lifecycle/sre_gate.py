"""Mandatory SRE approval gate before fullstack assembly."""

from __future__ import annotations

from app.models.sre_approval import SreApprovalRunStatus, SreStatus

SRE_APPROVED_STATUSES: frozenset[SreStatus] = frozenset(
    {
        SreStatus.SRE_APPROVED,
        SreStatus.SRE_APPROVED_WITH_WARNINGS,
    }
)

ASSEMBLY_SRE_GATE_MESSAGE = (
    "Finishing reliability checks. SRE production readiness must be approved before packaging."
)


def sre_status_from_artifact(artifact_json: dict) -> SreStatus | None:
    raw = artifact_json.get("sre_status")
    if raw is None:
        return None
    try:
        return SreStatus(raw)
    except ValueError:
        return None


def is_sre_approval_satisfied(*, run_status: str, sre_status: SreStatus | None) -> bool:
    if run_status != SreApprovalRunStatus.COMPLETED.value:
        return False
    return sre_status in SRE_APPROVED_STATUSES


def validate_sre_approval_for_assembly(*, run_status: str, sre_status: SreStatus | None) -> None:
    from app.core.exceptions import ValidationError

    if is_sre_approval_satisfied(run_status=run_status, sre_status=sre_status):
        return
    raise ValidationError(ASSEMBLY_SRE_GATE_MESSAGE)
