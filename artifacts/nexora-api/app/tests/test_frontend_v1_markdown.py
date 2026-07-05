from app.frontend_v1.markdown import output_to_markdown
from app.tests.conftest import mock_frontend_v1_output


def test_markdown_includes_title():
    md = output_to_markdown(mock_frontend_v1_output())
    assert "# Frontend Implementation Blueprint" in md


def test_markdown_includes_project_structure():
    md = output_to_markdown(mock_frontend_v1_output())
    assert "## Project Structure" in md


def test_markdown_includes_route_structure():
    md = output_to_markdown(mock_frontend_v1_output())
    assert "## Route Structure" in md


def test_markdown_includes_page_structure():
    md = output_to_markdown(mock_frontend_v1_output())
    assert "## Page Structure" in md


def test_markdown_includes_component_structure():
    md = output_to_markdown(mock_frontend_v1_output())
    assert "## Component Structure" in md


def test_markdown_includes_state_management():
    md = output_to_markdown(mock_frontend_v1_output())
    assert "## State Management Structure" in md


def test_markdown_includes_form_architecture():
    md = output_to_markdown(mock_frontend_v1_output())
    assert "## Form Architecture" in md


def test_markdown_includes_validation_strategy():
    md = output_to_markdown(mock_frontend_v1_output())
    assert "## Validation Strategy" in md


def test_markdown_includes_module_breakdown():
    md = output_to_markdown(mock_frontend_v1_output())
    assert "## Frontend Module Breakdown" in md
