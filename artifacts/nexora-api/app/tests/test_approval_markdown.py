from app.approval_workflow.markdown import output_to_markdown
from app.tests.conftest import mock_approval_workflow_output


def test_markdown_includes_title():
    md = output_to_markdown(mock_approval_workflow_output())
    assert "# Approval Workflow Package" in md


def test_markdown_includes_approval_status():
    md = output_to_markdown(mock_approval_workflow_output())
    assert "**Approval Status:**" in md
    assert "UNDER_REVIEW" in md


def test_markdown_includes_recommendation():
    md = output_to_markdown(mock_approval_workflow_output())
    assert "**Recommendation:**" in md


def test_markdown_includes_summary_section():
    md = output_to_markdown(mock_approval_workflow_output())
    assert "## Summary" in md


def test_markdown_includes_review_summary_section():
    md = output_to_markdown(mock_approval_workflow_output())
    assert "## Review Summary" in md
    assert "**Frontend Execution:**" in md
    assert "**Assembly:**" in md


def test_markdown_includes_approval_package_section():
    md = output_to_markdown(mock_approval_workflow_output())
    assert "## Approval Package" in md
    assert "generated-app" in md


def test_markdown_includes_checklist_section():
    md = output_to_markdown(mock_approval_workflow_output())
    assert "## Approval Checklist" in md
    assert "Frontend Execution" in md


def test_markdown_includes_deployment_readiness_section():
    md = output_to_markdown(mock_approval_workflow_output())
    assert "## Deployment Readiness Report" in md
    assert "**Ready for Deployment:**" in md
