from app.models.frontend_execution import FrontendExecutionApprovalStatus
from app.schemas.frontend_execution import FrontendExecutionOutput
from app.tests.conftest import mock_frontend_execution_output


def test_output_schema_defaults():
    output = FrontendExecutionOutput(
        build_status="failed",
        validation_status="failed",
        approval_status=FrontendExecutionApprovalStatus.FRONTEND_NEEDS_REVIEW.value,
    )
    assert output.execution_logs == []
    assert output.lint_results == {}
    assert output.build_results == {}


def test_mock_output_is_valid_schema():
    output = mock_frontend_execution_output()
    assert isinstance(output, FrontendExecutionOutput)
    dumped = output.model_dump()
    assert len(dumped["execution_logs"]) >= 1
    assert dumped["build_status"] == "success"


def test_output_serializes_step_results():
    output = mock_frontend_execution_output()
    for field in ("lint_results", "typecheck_results", "test_results", "build_results", "install_results"):
        results = output.model_dump()[field]
        assert "status" in results
        assert "exit_code" in results


def test_output_serializes_execution_logs():
    output = mock_frontend_execution_output()
    logs = output.model_dump()["execution_logs"]
    assert all(isinstance(entry, str) for entry in logs)


def test_output_serializes_approval_status():
    output = mock_frontend_execution_output()
    assert output.approval_status == FrontendExecutionApprovalStatus.FRONTEND_APPROVED.value
