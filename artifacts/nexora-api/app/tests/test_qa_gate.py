"""Unit tests for mandatory QA approval gate logic."""

import pytest

from app.core.exceptions import ValidationError
from app.lifecycle.qa_gate import (
    ASSEMBLY_QA_GATE_MESSAGE,
    is_qa_approval_satisfied,
    qa_status_from_artifact,
    validate_qa_approval_for_assembly,
)
from app.models.qa_approval import QAApprovalRunStatus, QAStatus


def test_qa_status_from_artifact_parses_valid_status():
    assert qa_status_from_artifact({"qa_status": "QA_APPROVED"}) == QAStatus.QA_APPROVED


def test_qa_status_from_artifact_returns_none_for_invalid():
    assert qa_status_from_artifact({"qa_status": "INVALID"}) is None
    assert qa_status_from_artifact({}) is None


@pytest.mark.parametrize(
    "qa_status",
    [QAStatus.QA_APPROVED, QAStatus.QA_APPROVED_WITH_WARNINGS],
)
def test_is_qa_approval_satisfied_for_approved_statuses(qa_status):
    assert is_qa_approval_satisfied(
        run_status=QAApprovalRunStatus.COMPLETED.value,
        qa_status=qa_status,
    )


@pytest.mark.parametrize(
    "run_status,qa_status",
    [
        (QAApprovalRunStatus.COMPLETED.value, QAStatus.QA_REJECTED),
        (QAApprovalRunStatus.FAILED.value, QAStatus.QA_APPROVED),
        (QAApprovalRunStatus.COMPLETED.value, None),
    ],
)
def test_is_qa_approval_not_satisfied(run_status, qa_status):
    assert not is_qa_approval_satisfied(run_status=run_status, qa_status=qa_status)


def test_validate_qa_approval_for_assembly_accepts_approved():
    validate_qa_approval_for_assembly(
        run_status=QAApprovalRunStatus.COMPLETED.value,
        qa_status=QAStatus.QA_APPROVED,
    )


def test_validate_qa_approval_for_assembly_accepts_approved_with_warnings():
    validate_qa_approval_for_assembly(
        run_status=QAApprovalRunStatus.COMPLETED.value,
        qa_status=QAStatus.QA_APPROVED_WITH_WARNINGS,
    )


def test_validate_qa_approval_for_assembly_rejects_missing():
    with pytest.raises(ValidationError, match=ASSEMBLY_QA_GATE_MESSAGE):
        validate_qa_approval_for_assembly(
            run_status=QAApprovalRunStatus.COMPLETED.value,
            qa_status=None,
        )


def test_validate_qa_approval_for_assembly_rejects_rejected():
    with pytest.raises(ValidationError, match=ASSEMBLY_QA_GATE_MESSAGE):
        validate_qa_approval_for_assembly(
            run_status=QAApprovalRunStatus.COMPLETED.value,
            qa_status=QAStatus.QA_REJECTED,
        )


def test_validate_qa_approval_for_assembly_rejects_incomplete_run():
    with pytest.raises(ValidationError, match=ASSEMBLY_QA_GATE_MESSAGE):
        validate_qa_approval_for_assembly(
            run_status=QAApprovalRunStatus.FAILED.value,
            qa_status=QAStatus.QA_APPROVED,
        )
