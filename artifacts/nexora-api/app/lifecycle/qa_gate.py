"""Mandatory QA approval gate before fullstack assembly."""

from __future__ import annotations

from app.models.qa_approval import QAApprovalRunStatus, QAStatus

QA_APPROVED_STATUSES: frozenset[QAStatus] = frozenset(
    {
        QAStatus.QA_APPROVED,
        QAStatus.QA_APPROVED_WITH_WARNINGS,
    }
)

ASSEMBLY_QA_GATE_MESSAGE = (
    "Finishing validation checks. Quality review must be approved before packaging."
)


def qa_status_from_artifact(artifact_json: dict) -> QAStatus | None:
    raw = artifact_json.get("qa_status")
    if raw is None:
        return None
    try:
        return QAStatus(raw)
    except ValueError:
        return None


def is_qa_approval_satisfied(*, run_status: str, qa_status: QAStatus | None) -> bool:
    if run_status != QAApprovalRunStatus.COMPLETED.value:
        return False
    return qa_status in QA_APPROVED_STATUSES


def validate_qa_approval_for_assembly(*, run_status: str, qa_status: QAStatus | None) -> None:
    from app.core.exceptions import ValidationError

    if is_qa_approval_satisfied(run_status=run_status, qa_status=qa_status):
        return
    if qa_status == QAStatus.QA_REJECTED:
        raise ValidationError(ASSEMBLY_QA_GATE_MESSAGE)
    raise ValidationError(ASSEMBLY_QA_GATE_MESSAGE)
