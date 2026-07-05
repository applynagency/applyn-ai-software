from app.deployment.markdown import output_to_markdown
from app.tests.conftest import mock_deployment_output


def test_markdown_includes_title():
    md = output_to_markdown(mock_deployment_output())
    assert "# Deployment Report" in md


def test_markdown_includes_provider():
    md = output_to_markdown(mock_deployment_output())
    assert "**Provider:**" in md
    assert "AZURE" in md


def test_markdown_includes_status():
    md = output_to_markdown(mock_deployment_output())
    assert "**Status:**" in md
    assert "DEPLOYED" in md


def test_markdown_includes_live_url():
    md = output_to_markdown(mock_deployment_output())
    assert "**Live URL:**" in md
    assert ".applyn.app" in md


def test_markdown_includes_rollback_flag():
    md = output_to_markdown(mock_deployment_output())
    assert "**Rollback Available:**" in md


def test_markdown_includes_summary_section():
    md = output_to_markdown(mock_deployment_output())
    assert "## Summary" in md


def test_markdown_includes_metadata_section():
    md = output_to_markdown(mock_deployment_output())
    assert "## Deployment Metadata" in md


def test_markdown_includes_logs_section():
    md = output_to_markdown(mock_deployment_output())
    assert "## Deployment Logs" in md
    assert "Azure" in md
