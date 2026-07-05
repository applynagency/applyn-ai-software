from app.backend_execution.validator import BackendExecutionValidator
from app.models.backend_execution import BackendExecutionApprovalStatus
from app.schemas.backend_execution import BackendExecutionOutput
from app.tests.conftest import mock_backend_execution_output


def test_validator_accepts_complete_output():
    validator = BackendExecutionValidator()
    result = validator.validate(mock_backend_execution_output())
    assert result.is_valid is True
    assert result.score >= 80


def test_validator_rejects_missing_build_status():
    validator = BackendExecutionValidator()
    output = BackendExecutionOutput.model_construct(
        build_status=None,
        validation_status="passed",
        execution_logs=["log"],
        approval_status=BackendExecutionApprovalStatus.BACKEND_APPROVED.value,
        startup_results={"status": "success"},
    )
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("build_status" in error for error in result.errors)


def test_validator_rejects_invalid_build_status():
    validator = BackendExecutionValidator()
    output = mock_backend_execution_output(build_status="unknown")
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("build_status" in error for error in result.errors)


def test_validator_rejects_missing_approval_status():
    validator = BackendExecutionValidator()
    output = BackendExecutionOutput.model_construct(
        build_status="success",
        validation_status="passed",
        execution_logs=["log"],
        approval_status=None,
        startup_results={"status": "success"},
    )
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("approval_status" in error for error in result.errors)


def test_validator_rejects_invalid_approval_status():
    validator = BackendExecutionValidator()
    output = mock_backend_execution_output(approval_status="INVALID_STATUS")
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("approval_status" in error for error in result.errors)


def test_validator_rejects_missing_execution_logs():
    validator = BackendExecutionValidator()
    output = BackendExecutionOutput.model_construct(
        build_status="success",
        validation_status="passed",
        execution_logs=None,
        approval_status=BackendExecutionApprovalStatus.BACKEND_APPROVED.value,
        startup_results={"status": "success"},
    )
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("execution_logs" in error for error in result.errors)


def test_validator_rejects_empty_execution_logs():
    validator = BackendExecutionValidator()
    output = mock_backend_execution_output(execution_logs=[])
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("execution_logs" in error for error in result.errors)


def test_validator_rejects_missing_validation_status():
    validator = BackendExecutionValidator()
    output = BackendExecutionOutput.model_construct(
        build_status="success",
        validation_status=None,
        execution_logs=["log"],
        approval_status=BackendExecutionApprovalStatus.BACKEND_APPROVED.value,
        startup_results={"status": "success"},
    )
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("validation_status" in error for error in result.errors)


def test_validator_rejects_missing_startup_results_on_success():
    validator = BackendExecutionValidator()
    output = mock_backend_execution_output(build_status="success", startup_results={})
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("startup_results" in error for error in result.errors)


def test_validator_accepts_failed_build_without_startup_results():
    validator = BackendExecutionValidator()
    output = mock_backend_execution_output(
        build_status="failed",
        startup_results={},
        approval_status=BackendExecutionApprovalStatus.BACKEND_NEEDS_REVIEW.value,
    )
    result = validator.validate(output)
    assert result.is_valid is True


def test_validator_counts_are_reported():
    validator = BackendExecutionValidator()
    result = validator.validate(mock_backend_execution_output())
    assert result.counts["log_count"] >= 1
    assert result.counts["has_build_status"] is True
    assert result.counts["has_approval_status"] is True
    assert result.counts["has_validation_status"] is True
    assert result.counts["ruff_status"] == "success"


def test_validator_accepts_all_valid_approval_statuses():
    validator = BackendExecutionValidator()
    for status in BackendExecutionApprovalStatus:
        output = mock_backend_execution_output(approval_status=status.value)
        result = validator.validate(output)
        assert result.is_valid is True, f"Expected valid for {status.value}"
