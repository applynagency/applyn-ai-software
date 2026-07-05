from app.backend_execution.markdown import output_to_markdown
from app.models.backend_execution import BackendExecutionApprovalStatus
from app.schemas.backend_execution import BackendExecutionOutput
from app.tests.conftest import mock_backend_execution_output


def test_markdown_includes_ruff_results_section():
    md = output_to_markdown(mock_backend_execution_output())
    assert "## Ruff Results" in md
    assert "ruff check" in md


def test_markdown_includes_mypy_results_section():
    md = output_to_markdown(mock_backend_execution_output())
    assert "## MyPy Results" in md
    assert "mypy" in md


def test_markdown_includes_test_results_section():
    md = output_to_markdown(mock_backend_execution_output())
    assert "## Pytest Results" in md
    assert "pytest" in md


def test_markdown_shows_not_executed_for_missing_step():
    output = BackendExecutionOutput(
        build_status="failed",
        validation_status="failed",
        execution_logs=["pip install failed"],
        approval_status=BackendExecutionApprovalStatus.BACKEND_NEEDS_REVIEW.value,
        startup_results={"status": "failed", "exit_code": 1},
        pytest_results={"status": "skipped", "exit_code": 0},
    )
    md = output_to_markdown(output)
    assert "_Not executed._" in md


def test_markdown_includes_step_exit_code():
    md = output_to_markdown(mock_backend_execution_output())
    assert "**Exit Code:**" in md
    assert "0" in md


def test_markdown_includes_step_duration():
    output = mock_backend_execution_output()
    output = output.model_copy(
        update={"ruff_results": {**output.ruff_results, "duration_ms": 800}}
    )
    md = output_to_markdown(output)
    assert "**Duration:**" in md
    assert "800ms" in md
