from app.business_analyst.markdown import output_to_markdown
from app.tests.conftest import mock_business_analyst_output


def test_markdown_includes_title():
    md = output_to_markdown(mock_business_analyst_output())
    assert "# Business Analysis Document" in md


def test_markdown_includes_functional_requirements():
    md = output_to_markdown(mock_business_analyst_output())
    assert "## Functional Requirements" in md
    assert "FR-1" in md


def test_markdown_includes_modules():
    md = output_to_markdown(mock_business_analyst_output())
    assert "## Modules" in md


def test_markdown_includes_roles():
    md = output_to_markdown(mock_business_analyst_output())
    assert "## Roles" in md


def test_markdown_includes_user_flows():
    md = output_to_markdown(mock_business_analyst_output())
    assert "## User Flows" in md


def test_markdown_includes_business_rules():
    md = output_to_markdown(mock_business_analyst_output())
    assert "## Business Rules" in md


def test_markdown_includes_acceptance_criteria():
    md = output_to_markdown(mock_business_analyst_output())
    assert "## Acceptance Criteria" in md


def test_markdown_includes_project_summary():
    md = output_to_markdown(mock_business_analyst_output())
    assert "## Project Summary" in md
