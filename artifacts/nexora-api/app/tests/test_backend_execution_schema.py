from app.models.backend_execution import BackendExecutionApprovalStatus
from app.schemas.backend_execution import BackendExecutionOutput
from app.tests.conftest import mock_backend_execution_output


def test_output_schema_defaults():
    output = BackendExecutionOutput(
        build_status="failed",
        validation_status="failed",
        approval_status=BackendExecutionApprovalStatus.BACKEND_NEEDS_REVIEW.value,
    )
    assert output.execution_logs == []
    assert output.ruff_results == {}
    assert output.startup_results == {}


def test_mock_output_is_valid_schema():
    output = mock_backend_execution_output()
    assert isinstance(output, BackendExecutionOutput)
    dumped = output.model_dump()
    assert len(dumped["execution_logs"]) >= 1
    assert dumped["build_status"] == "success"


def test_output_serializes_step_results():
    output = mock_backend_execution_output()
    for field in ("ruff_results", "mypy_results", "pytest_results", "startup_results", "dependency_results"):
        results = output.model_dump()[field]
        assert "status" in results
        assert "exit_code" in results


def test_output_serializes_execution_logs():
    output = mock_backend_execution_output()
    logs = output.model_dump()["execution_logs"]
    assert all(isinstance(entry, str) for entry in logs)


def test_output_serializes_approval_status():
    output = mock_backend_execution_output()
    assert output.approval_status == BackendExecutionApprovalStatus.BACKEND_APPROVED.value
