from app.cicd_agent.markdown import output_to_markdown
from app.tests.conftest import mock_cicd_agent_output


def test_markdown_includes_title():
    md = output_to_markdown(mock_cicd_agent_output())
    assert "# CI/CD Pipeline Blueprint" in md


def test_markdown_includes_github_actions():
    md = output_to_markdown(mock_cicd_agent_output())
    assert "## GitHub Actions" in md


def test_markdown_includes_azure_devops():
    md = output_to_markdown(mock_cicd_agent_output())
    assert "## Azure DevOps" in md


def test_markdown_includes_gitlab_ci():
    md = output_to_markdown(mock_cicd_agent_output())
    assert "## GitLab CI" in md


def test_markdown_includes_rollback_strategy():
    md = output_to_markdown(mock_cicd_agent_output())
    assert "## Rollback Strategy" in md
