from app.approval_workflow.validator import ApprovalWorkflowValidator
from app.models.approval import ApprovalRecommendation, WorkflowApprovalStatus
from app.schemas.approval import ApprovalWorkflowOutput
from app.tests.conftest import mock_approval_workflow_output


def test_validator_accepts_complete_output():
    validator = ApprovalWorkflowValidator()
    result = validator.validate(
        mock_approval_workflow_output(),
        frontend_execution_approved=True,
        assembly_approved=True,
    )
    assert result.is_valid is True
    assert result.score >= 80


def test_validator_rejects_unapproved_frontend_execution():
    validator = ApprovalWorkflowValidator()
    result = validator.validate(
        mock_approval_workflow_output(),
        frontend_execution_approved=False,
        assembly_approved=True,
    )
    assert result.is_valid is False
    assert any("Frontend Execution" in error for error in result.errors)


def test_validator_rejects_unapproved_assembly():
    validator = ApprovalWorkflowValidator()
    result = validator.validate(
        mock_approval_workflow_output(),
        frontend_execution_approved=True,
        assembly_approved=False,
    )
    assert result.is_valid is False
    assert any("Full Stack Assembly" in error for error in result.errors)


def test_validator_rejects_missing_frontend_review_status():
    validator = ApprovalWorkflowValidator()
    output = mock_approval_workflow_output()
    summary = dict(output.approval_summary)
    review_summary = dict(summary.get("review_summary") or {})
    review_summary.pop("frontend_review_status", None)
    summary["review_summary"] = review_summary
    output = ApprovalWorkflowOutput.model_construct(
        **{**output.model_dump(), "approval_summary": summary}
    )
    result = validator.validate(
        output,
        frontend_execution_approved=True,
        assembly_approved=True,
    )
    assert result.is_valid is False
    assert any("Frontend review status" in error for error in result.errors)


def test_validator_rejects_missing_recommendation():
    validator = ApprovalWorkflowValidator()
    output = ApprovalWorkflowOutput.model_construct(
        **{**mock_approval_workflow_output().model_dump(), "recommendation": ""}
    )
    result = validator.validate(
        output,
        frontend_execution_approved=True,
        assembly_approved=True,
    )
    assert result.is_valid is False
    assert any("recommendation" in error for error in result.errors)


def test_validator_rejects_invalid_recommendation():
    validator = ApprovalWorkflowValidator()
    output = mock_approval_workflow_output(recommendation="INVALID")
    result = validator.validate(
        output,
        frontend_execution_approved=True,
        assembly_approved=True,
    )
    assert result.is_valid is False
    assert any("recommendation" in error for error in result.errors)


def test_validator_rejects_missing_review_checklist():
    validator = ApprovalWorkflowValidator()
    output = ApprovalWorkflowOutput.model_construct(
        **{**mock_approval_workflow_output().model_dump(), "review_checklist": []}
    )
    result = validator.validate(
        output,
        frontend_execution_approved=True,
        assembly_approved=True,
    )
    assert result.is_valid is False
    assert any("review_checklist" in error for error in result.errors)


def test_validator_rejects_missing_deployment_readiness():
    validator = ApprovalWorkflowValidator()
    output = ApprovalWorkflowOutput.model_construct(
        **{**mock_approval_workflow_output().model_dump(), "deployment_readiness": {}}
    )
    result = validator.validate(
        output,
        frontend_execution_approved=True,
        assembly_approved=True,
    )
    assert result.is_valid is False
    assert any("deployment_readiness" in error for error in result.errors)


def test_validator_rejects_invalid_approval_status():
    validator = ApprovalWorkflowValidator()
    output = mock_approval_workflow_output(approval_status="INVALID_STATUS")
    result = validator.validate(
        output,
        frontend_execution_approved=True,
        assembly_approved=True,
    )
    assert result.is_valid is False
    assert any("approval_status" in error for error in result.errors)


def test_validator_accepts_all_valid_approval_statuses():
    validator = ApprovalWorkflowValidator()
    for status in WorkflowApprovalStatus:
        output = mock_approval_workflow_output(approval_status=status.value)
        result = validator.validate(
            output,
            frontend_execution_approved=True,
            assembly_approved=True,
        )
        assert result.is_valid is True, f"Expected valid for {status.value}"


def test_validator_accepts_all_valid_recommendations():
    validator = ApprovalWorkflowValidator()
    for recommendation in ApprovalRecommendation:
        output = mock_approval_workflow_output(recommendation=recommendation.value)
        result = validator.validate(
            output,
            frontend_execution_approved=True,
            assembly_approved=True,
        )
        assert result.is_valid is True, f"Expected valid for {recommendation.value}"


def test_validator_counts_are_reported():
    validator = ApprovalWorkflowValidator()
    output = mock_approval_workflow_output()
    result = validator.validate(
        output,
        frontend_execution_approved=True,
        assembly_approved=True,
    )
    assert result.counts["frontend_execution_approved"] is True
    assert result.counts["assembly_approved"] is True
    assert result.counts["checklist_item_count"] == 8
    assert result.counts["has_recommendation"] is True
