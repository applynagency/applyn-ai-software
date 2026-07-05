from app.backend_execution.markdown import output_to_markdown
from app.tests.conftest import mock_backend_execution_output


def test_markdown_includes_title():
    md = output_to_markdown(mock_backend_execution_output())
    assert "# Backend Execution Report" in md


def test_markdown_includes_build_status():
    md = output_to_markdown(mock_backend_execution_output())
    assert "**Build Status:**" in md
    assert "success" in md


def test_markdown_includes_validation_status():
    md = output_to_markdown(mock_backend_execution_output())
    assert "**Validation Status:**" in md
    assert "passed" in md


def test_markdown_includes_approval_status():
    md = output_to_markdown(mock_backend_execution_output())
    assert "**Approval Status:**" in md
    assert "BACKEND_APPROVED" in md


def test_markdown_includes_summary_section():
    md = output_to_markdown(mock_backend_execution_output())
    assert "## Summary" in md


def test_markdown_includes_dependency_results_section():
    md = output_to_markdown(mock_backend_execution_output())
    assert "## Dependency Verification" in md


def test_markdown_includes_startup_results_section():
    md = output_to_markdown(mock_backend_execution_output())
    assert "## Startup Validation" in md


def test_markdown_includes_execution_logs_section():
    md = output_to_markdown(mock_backend_execution_output())
    assert "## Execution Logs" in md
    assert "pip install" in md
