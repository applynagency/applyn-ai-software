from app.frontend_execution.markdown import output_to_markdown
from app.models.frontend_execution import FrontendExecutionApprovalStatus
from app.schemas.frontend_execution import FrontendExecutionOutput
from app.tests.conftest import mock_frontend_execution_output


def test_markdown_includes_lint_results_section():
    md = output_to_markdown(mock_frontend_execution_output())
    assert "## Lint Results" in md
    assert "npm run lint" in md


def test_markdown_includes_typecheck_results_section():
    md = output_to_markdown(mock_frontend_execution_output())
    assert "## Type Check Results" in md
    assert "npm run type-check" in md


def test_markdown_includes_test_results_section():
    md = output_to_markdown(mock_frontend_execution_output())
    assert "## Test Results" in md
    assert "npm test" in md


def test_markdown_shows_not_executed_for_missing_step():
    output = FrontendExecutionOutput(
        build_status="failed",
        validation_status="failed",
        execution_logs=["install failed"],
        approval_status=FrontendExecutionApprovalStatus.FRONTEND_NEEDS_REVIEW.value,
        install_results={"status": "failed", "exit_code": 1},
    )
    md = output_to_markdown(output)
    assert "_Not executed._" in md


def test_markdown_includes_step_exit_code():
    md = output_to_markdown(mock_frontend_execution_output())
    assert "**Exit Code:**" in md
    assert "0" in md


def test_markdown_includes_step_duration():
    output = mock_frontend_execution_output()
    output = output.model_copy(
        update={"lint_results": {**output.lint_results, "duration_ms": 800}}
    )
    md = output_to_markdown(output)
    assert "**Duration:**" in md
    assert "800ms" in md
