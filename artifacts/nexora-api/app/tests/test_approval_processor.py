from app.approval_workflow.processor import (
    PROCESSOR_VERSION,
    ApprovalWorkflowProcessor,
)
from app.models.approval import ApprovalRecommendation, WorkflowApprovalStatus
from app.models.frontend_code_review import ApprovalStatus as CodeReviewApprovalStatus
from app.models.frontend_execution import FrontendExecutionApprovalStatus
from app.models.fullstack_assembly import AssemblyStatus
from app.tests.conftest import (
    mock_frontend_code_review_output,
    mock_frontend_execution_output,
    mock_fullstack_assembly_output,
)


def _fe_output(**overrides) -> dict:
    return mock_frontend_execution_output(**overrides).model_dump()


def _fcr_output(**overrides) -> dict:
    return mock_frontend_code_review_output(**overrides).model_dump(mode="json")


def _fsa_output(**overrides) -> dict:
    return mock_fullstack_assembly_output(**overrides).model_dump()


def test_processor_version_constant():
    assert PROCESSOR_VERSION == "1.0.0"
    assert ApprovalWorkflowProcessor.get_processor_version() == PROCESSOR_VERSION


def test_process_returns_under_review_status():
    processor = ApprovalWorkflowProcessor()
    output = processor.process(
        frontend_execution_output=_fe_output(),
        frontend_code_review_output=_fcr_output(),
        fullstack_assembly_output=_fsa_output(),
        requirement_text="Approval gate requirement",
    )
    assert output.approval_status == WorkflowApprovalStatus.UNDER_REVIEW.value


def test_process_recommends_approve_when_all_upstream_approved():
    processor = ApprovalWorkflowProcessor()
    output = processor.process(
        frontend_execution_output=_fe_output(),
        frontend_code_review_output=_fcr_output(
            approval_status=CodeReviewApprovalStatus.APPROVED.value
        ),
        fullstack_assembly_output=_fsa_output(),
    )
    assert output.recommendation == ApprovalRecommendation.APPROVE.value


def test_process_recommends_review_with_execution_warnings():
    processor = ApprovalWorkflowProcessor()
    output = processor.process(
        frontend_execution_output=_fe_output(
            approval_status=FrontendExecutionApprovalStatus.FRONTEND_APPROVED_WITH_WARNINGS.value
        ),
        frontend_code_review_output=_fcr_output(),
        fullstack_assembly_output=_fsa_output(
            assembly_status=AssemblyStatus.ASSEMBLY_APPROVED_WITH_WARNINGS.value
        ),
    )
    assert output.recommendation == ApprovalRecommendation.REVIEW.value


def test_process_recommends_reject_when_code_review_rejected():
    processor = ApprovalWorkflowProcessor()
    output = processor.process(
        frontend_execution_output=_fe_output(),
        frontend_code_review_output=_fcr_output(
            approval_status=CodeReviewApprovalStatus.REJECTED.value
        ),
        fullstack_assembly_output=_fsa_output(),
    )
    assert output.recommendation == ApprovalRecommendation.REJECT.value


def test_process_recommends_reject_when_assembly_needs_review():
    processor = ApprovalWorkflowProcessor()
    output = processor.process(
        frontend_execution_output=_fe_output(),
        frontend_code_review_output=_fcr_output(),
        fullstack_assembly_output=_fsa_output(
            assembly_status=AssemblyStatus.ASSEMBLY_NEEDS_REVIEW.value
        ),
    )
    assert output.recommendation == ApprovalRecommendation.REJECT.value


def test_process_builds_review_checklist():
    processor = ApprovalWorkflowProcessor()
    output = processor.process(
        frontend_execution_output=_fe_output(),
        frontend_code_review_output=_fcr_output(),
        fullstack_assembly_output=_fsa_output(),
    )
    assert len(output.review_checklist) == 8
    checklist_ids = {item["id"] for item in output.review_checklist}
    assert "CHK-FE-001" in checklist_ids
    assert "CHK-ASM-002" in checklist_ids
    assert "CHK-DEP-002" in checklist_ids


def test_process_deployment_readiness_ready_when_all_passed():
    processor = ApprovalWorkflowProcessor()
    output = processor.process(
        frontend_execution_output=_fe_output(),
        frontend_code_review_output=_fcr_output(),
        fullstack_assembly_output=_fsa_output(),
    )
    readiness = output.deployment_readiness
    assert readiness["ready_for_deployment"] is True
    assert readiness["readiness_score"] == 100.0
    assert readiness["blocking_issues"] == []


def test_process_deployment_readiness_not_ready_without_docker():
    processor = ApprovalWorkflowProcessor()
    fsa = _fsa_output()
    fsa["docker_assets"] = {}
    output = processor.process(
        frontend_execution_output=_fe_output(),
        frontend_code_review_output=_fcr_output(),
        fullstack_assembly_output=fsa,
    )
    assert output.deployment_readiness["ready_for_deployment"] is False
    assert "Docker assets present" in output.deployment_readiness["blocking_issues"]


def test_process_approval_summary_includes_upstream_statuses():
    processor = ApprovalWorkflowProcessor()
    output = processor.process(
        frontend_execution_output=_fe_output(),
        frontend_code_review_output=_fcr_output(
            approval_status=CodeReviewApprovalStatus.APPROVED.value
        ),
        fullstack_assembly_output=_fsa_output(),
        requirement_text="Long requirement text for excerpt",
    )
    review_summary = output.approval_summary["review_summary"]
    assert review_summary["frontend_execution_status"] == "FRONTEND_APPROVED"
    assert review_summary["frontend_review_status"] == "APPROVED"
    assert review_summary["assembly_status"] == AssemblyStatus.ASSEMBLY_APPROVED.value


def test_process_approval_package_includes_manifest_metadata():
    processor = ApprovalWorkflowProcessor()
    output = processor.process(
        frontend_execution_output=_fe_output(),
        frontend_code_review_output=_fcr_output(),
        fullstack_assembly_output=_fsa_output(),
    )
    package = output.approval_summary["approval_package"]
    assert package["name"] == "generated-app"
    assert package["backend_included"] is True
    assert package["environment_variable_count"] >= 1


def test_process_readiness_flags_upstream_approval_state():
    processor = ApprovalWorkflowProcessor()
    output = processor.process(
        frontend_execution_output=_fe_output(),
        frontend_code_review_output=_fcr_output(),
        fullstack_assembly_output=_fsa_output(),
    )
    readiness_flags = output.approval_summary["approval_readiness"]
    assert readiness_flags["frontend_execution_approved"] is True
    assert readiness_flags["frontend_review_approved"] is True
    assert readiness_flags["assembly_approved"] is True
