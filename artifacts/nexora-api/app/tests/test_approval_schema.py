from app.models.approval import (
    ApprovalRecommendation,
    ApprovalRunStatus,
    WorkflowApprovalStatus,
)
from app.schemas.approval import ApprovalWorkflowOutput
from app.tests.conftest import mock_approval_workflow_output


def test_output_schema_requires_recommendation_and_status():
    output = ApprovalWorkflowOutput(
        recommendation=ApprovalRecommendation.APPROVE.value,
        approval_status=WorkflowApprovalStatus.UNDER_REVIEW.value,
    )
    assert output.approval_summary == {}
    assert output.review_checklist == []


def test_mock_output_is_valid_schema():
    output = mock_approval_workflow_output()
    assert isinstance(output, ApprovalWorkflowOutput)
    dumped = output.model_dump()
    assert dumped["approval_status"] == WorkflowApprovalStatus.UNDER_REVIEW.value
    assert dumped["recommendation"] in {item.value for item in ApprovalRecommendation}


def test_output_serializes_package_sections():
    output = mock_approval_workflow_output()
    for key in (
        "approval_summary",
        "review_checklist",
        "deployment_readiness",
        "recommendation",
        "approval_status",
    ):
        assert key in output.model_dump()


def test_run_status_enum_values():
    assert ApprovalRunStatus.PENDING.value == "PENDING"
    assert ApprovalRunStatus.RUNNING.value == "RUNNING"
    assert ApprovalRunStatus.COMPLETED.value == "COMPLETED"
    assert ApprovalRunStatus.FAILED.value == "FAILED"


def test_workflow_approval_status_enum_values():
    assert WorkflowApprovalStatus.UNDER_REVIEW.value == "UNDER_REVIEW"
    assert WorkflowApprovalStatus.APPROVED.value == "APPROVED"
    assert WorkflowApprovalStatus.REJECTED.value == "REJECTED"
    assert WorkflowApprovalStatus.DEPLOYED.value == "DEPLOYED"
