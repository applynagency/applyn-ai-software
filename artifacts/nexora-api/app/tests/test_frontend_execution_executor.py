from unittest.mock import patch

import pytest

from app.core.exceptions import AgentError
from app.frontend_execution.executor import FrontendExecutionExecutor
from app.models.frontend_execution import FrontendExecutionApprovalStatus


def _sample_v3_output(*, files: list[dict] | None = None) -> dict:
    return {
        "generated_files": files
        or [
            {"path": "package.json", "content": '{"name":"demo"}'},
            {"path": "src/index.ts", "content": "export const ok = true;"},
        ]
    }


def _sample_review_output(*, approval_status: str = "APPROVED") -> dict:
    return {"approval_status": approval_status}


def test_write_generated_files_creates_paths(tmp_path):
    executor = FrontendExecutionExecutor()
    v3_output = _sample_v3_output()
    executor._write_generated_files(tmp_path, v3_output)
    assert (tmp_path / "package.json").exists()
    assert (tmp_path / "src/index.ts").read_text() == "export const ok = true;"


def test_write_generated_files_raises_on_empty_files(tmp_path):
    executor = FrontendExecutionExecutor()
    with pytest.raises(AgentError, match="no generated files"):
        executor._write_generated_files(tmp_path, {"generated_files": []})


def test_derive_approval_status_approved():
    executor = FrontendExecutionExecutor()
    status = executor._derive_approval_status(
        build_status="success",
        validation_status="passed",
        frontend_code_review_output=_sample_review_output(approval_status="APPROVED"),
    )
    assert status == FrontendExecutionApprovalStatus.FRONTEND_APPROVED.value


def test_derive_approval_status_approved_with_warnings():
    executor = FrontendExecutionExecutor()
    status = executor._derive_approval_status(
        build_status="success",
        validation_status="passed",
        frontend_code_review_output=_sample_review_output(
            approval_status="APPROVED_WITH_WARNINGS"
        ),
    )
    assert status == FrontendExecutionApprovalStatus.FRONTEND_APPROVED_WITH_WARNINGS.value


def test_derive_approval_status_needs_review_on_build_failure():
    executor = FrontendExecutionExecutor()
    status = executor._derive_approval_status(
        build_status="failed",
        validation_status="failed",
        frontend_code_review_output=_sample_review_output(approval_status="APPROVED"),
    )
    assert status == FrontendExecutionApprovalStatus.FRONTEND_NEEDS_REVIEW.value


def test_derive_approval_status_needs_review_on_code_review_rejection():
    executor = FrontendExecutionExecutor()
    status = executor._derive_approval_status(
        build_status="success",
        validation_status="passed",
        frontend_code_review_output=_sample_review_output(approval_status="REJECTED"),
    )
    assert status == FrontendExecutionApprovalStatus.FRONTEND_NEEDS_REVIEW.value


def test_derive_validation_status_passed():
    executor = FrontendExecutionExecutor()
    status = executor._derive_validation_status(
        {
            "install": {"status": "success"},
            "lint": {"status": "success"},
            "build": {"status": "success"},
        }
    )
    assert status == "passed"


def test_derive_validation_status_failed_on_critical_step():
    executor = FrontendExecutionExecutor()
    status = executor._derive_validation_status(
        {
            "install": {"status": "success"},
            "build": {"status": "failed"},
            "lint": {"status": "success"},
        }
    )
    assert status == "failed"


def test_derive_validation_status_warnings_on_non_critical_failure():
    executor = FrontendExecutionExecutor()
    status = executor._derive_validation_status(
        {
            "install": {"status": "success"},
            "build": {"status": "success"},
            "lint": {"status": "failed"},
            "test": {"status": "failed"},
        }
    )
    assert status == "warnings"


def test_execute_sync_returns_structured_output():
    executor = FrontendExecutionExecutor()
    step_result = {"status": "success", "exit_code": 0, "duration_ms": 10, "command": "cmd"}

    with patch.object(executor, "_run_command", return_value=step_result):
        output = executor.execute_sync(
            frontend_v3_output=_sample_v3_output(),
            frontend_code_review_output=_sample_review_output(),
        )

    assert output.build_status == "success"
    assert output.validation_status == "passed"
    assert output.execution_logs
    assert isinstance(output.approval_status, str)
