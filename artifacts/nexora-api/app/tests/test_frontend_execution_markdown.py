from app.frontend_execution.markdown import output_to_markdown
from app.tests.conftest import mock_frontend_execution_output


def test_markdown_includes_title():
    md = output_to_markdown(mock_frontend_execution_output())
    assert "# Frontend Execution Report" in md


def test_markdown_includes_build_status():
    md = output_to_markdown(mock_frontend_execution_output())
    assert "**Build Status:**" in md
    assert "success" in md


def test_markdown_includes_validation_status():
    md = output_to_markdown(mock_frontend_execution_output())
    assert "**Validation Status:**" in md
    assert "passed" in md


def test_markdown_includes_approval_status():
    md = output_to_markdown(mock_frontend_execution_output())
    assert "**Approval Status:**" in md
    assert "FRONTEND_APPROVED" in md


def test_markdown_includes_summary_section():
    md = output_to_markdown(mock_frontend_execution_output())
    assert "## Summary" in md


def test_markdown_includes_install_results_section():
    md = output_to_markdown(mock_frontend_execution_output())
    assert "## Install Results" in md


def test_markdown_includes_build_results_section():
    md = output_to_markdown(mock_frontend_execution_output())
    assert "## Build Results" in md


def test_markdown_includes_execution_logs_section():
    md = output_to_markdown(mock_frontend_execution_output())
    assert "## Execution Logs" in md
    assert "npm install" in md
