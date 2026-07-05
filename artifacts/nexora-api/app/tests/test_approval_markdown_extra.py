from app.approval_workflow.markdown import output_to_markdown
from app.tests.conftest import mock_approval_workflow_output


def test_markdown_includes_review_score_when_present():
    md = output_to_markdown(mock_approval_workflow_output())
    assert "**Review Score:**" in md


def test_markdown_includes_backend_included_flag():
    md = output_to_markdown(mock_approval_workflow_output())
    assert "**Backend Included:**" in md
    assert "True" in md


def test_markdown_includes_environment_variable_count():
    md = output_to_markdown(mock_approval_workflow_output())
    assert "**Environment Variables:**" in md


def test_markdown_shows_checklist_status_markers():
    md = output_to_markdown(mock_approval_workflow_output())
    assert "[PASSED]" in md or "[FAILED]" in md


def test_markdown_includes_readiness_score():
    md = output_to_markdown(mock_approval_workflow_output())
    assert "**Readiness Score:**" in md


def test_markdown_ends_with_trailing_newline():
    md = output_to_markdown(mock_approval_workflow_output())
    assert md.endswith("\n")
