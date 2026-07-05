from unittest.mock import patch

import pytest

from app.backend_execution.executor import BackendExecutionExecutor
from app.core.exceptions import AgentError
from app.models.backend_execution import BackendExecutionApprovalStatus


def _sample_v3_output(*, files: list[dict] | None = None) -> dict:
    return {
        "generated_files": files
        or [
            {"path": "requirements.txt", "content": "fastapi>=0.110.0\npytest>=8.0.0\n"},
            {"path": "app/__init__.py", "content": ""},
            {"path": "app/main.py", "content": "from fastapi import FastAPI\napp = FastAPI(title='Demo')\n"},
            {"path": "app/core/config.py", "content": "class Settings:\n    database_url = 'sqlite:///./test.db'\nsettings = Settings()\n"},
        ]
    }


def _sample_review_output(*, approval_status: str = "APPROVED") -> dict:
    return {"approval_status": approval_status}


def test_write_generated_files_creates_paths(tmp_path):
    executor = BackendExecutionExecutor()
    v3_output = _sample_v3_output()
    executor._write_generated_files(tmp_path, v3_output)
    assert (tmp_path / "requirements.txt").exists()
    assert (tmp_path / "app/main.py").exists()


def test_write_generated_files_raises_on_empty_files(tmp_path):
    executor = BackendExecutionExecutor()
    with pytest.raises(AgentError, match="no generated files"):
        executor._write_generated_files(tmp_path, {"generated_files": []})


def test_derive_approval_status_approved():
    executor = BackendExecutionExecutor()
    status = executor._derive_approval_status(
        build_status="success",
        validation_status="passed",
        backend_code_review_output=_sample_review_output(approval_status="APPROVED"),
    )
    assert status == BackendExecutionApprovalStatus.BACKEND_APPROVED.value


def test_derive_approval_status_approved_with_warnings():
    executor = BackendExecutionExecutor()
    status = executor._derive_approval_status(
        build_status="success",
        validation_status="passed",
        backend_code_review_output=_sample_review_output(
            approval_status="APPROVED_WITH_WARNINGS"
        ),
    )
    assert status == BackendExecutionApprovalStatus.BACKEND_APPROVED_WITH_WARNINGS.value


def test_derive_approval_status_needs_review_on_build_failure():
    executor = BackendExecutionExecutor()
    status = executor._derive_approval_status(
        build_status="failed",
        validation_status="failed",
        backend_code_review_output=_sample_review_output(approval_status="APPROVED"),
    )
    assert status == BackendExecutionApprovalStatus.BACKEND_NEEDS_REVIEW.value


def test_derive_approval_status_needs_review_on_code_review_rejection():
    executor = BackendExecutionExecutor()
    status = executor._derive_approval_status(
        build_status="success",
        validation_status="passed",
        backend_code_review_output=_sample_review_output(approval_status="REJECTED"),
    )
    assert status == BackendExecutionApprovalStatus.BACKEND_NEEDS_REVIEW.value


def test_derive_validation_status_passed():
    executor = BackendExecutionExecutor()
    status = executor._derive_validation_status(
        {
            "pip_install": {"status": "success"},
            "startup": {"status": "success"},
            "ruff": {"status": "success"},
        }
    )
    assert status == "passed"


def test_derive_validation_status_failed_on_critical_step():
    executor = BackendExecutionExecutor()
    status = executor._derive_validation_status(
        {
            "pip_install": {"status": "success"},
            "startup": {"status": "failed"},
            "ruff": {"status": "success"},
        }
    )
    assert status == "failed"


def test_derive_validation_status_warnings_on_non_critical_failure():
    executor = BackendExecutionExecutor()
    status = executor._derive_validation_status(
        {
            "pip_install": {"status": "success"},
            "startup": {"status": "success"},
            "ruff": {"status": "failed"},
            "mypy": {"status": "failed"},
        }
    )
    assert status == "warnings"


def test_derive_build_status_success():
    executor = BackendExecutionExecutor()
    assert executor._derive_build_status(
        {"pip_install": {"status": "success"}, "startup": {"status": "success"}}
    ) == "success"


def test_derive_build_status_failed_on_pip_install():
    executor = BackendExecutionExecutor()
    assert executor._derive_build_status({"pip_install": {"status": "failed"}}) == "failed"


def test_should_skip_alembic_without_ini(tmp_path):
    executor = BackendExecutionExecutor()
    assert executor._should_skip_step(tmp_path, "alembic") is True
    (tmp_path / "alembic.ini").write_text("[alembic]\n")
    assert executor._should_skip_step(tmp_path, "alembic") is False


def test_execute_sync_returns_structured_output():
    executor = BackendExecutionExecutor()
    step_result = {"status": "success", "exit_code": 0, "duration_ms": 10, "command": "cmd"}

    with patch.object(executor, "_run_command", return_value=step_result):
        output = executor.execute_sync(
            backend_v3_output=_sample_v3_output(),
            backend_code_review_output=_sample_review_output(),
        )

    assert output.build_status == "success"
    assert output.validation_status == "passed"
    assert output.execution_logs
    assert output.ruff_results
    assert output.pytest_results
    assert output.startup_results
    assert isinstance(output.approval_status, str)
