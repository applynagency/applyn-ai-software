from app.frontend_architect.markdown import output_to_markdown
from app.tests.conftest import mock_frontend_architect_output


def test_markdown_includes_title():
    md = output_to_markdown(mock_frontend_architect_output())
    assert "# Frontend Architecture Blueprint" in md


def test_markdown_includes_frontend_stack():
    md = output_to_markdown(mock_frontend_architect_output())
    assert "## Frontend Technology Stack" in md


def test_markdown_includes_routing_architecture():
    md = output_to_markdown(mock_frontend_architect_output())
    assert "## Routing Architecture" in md


def test_markdown_includes_page_architecture():
    md = output_to_markdown(mock_frontend_architect_output())
    assert "## Page Architecture" in md


def test_markdown_includes_component_architecture():
    md = output_to_markdown(mock_frontend_architect_output())
    assert "## Component Architecture" in md


def test_markdown_includes_api_integration():
    md = output_to_markdown(mock_frontend_architect_output())
    assert "## API Integration Architecture" in md


def test_markdown_includes_form_architecture():
    md = output_to_markdown(mock_frontend_architect_output())
    assert "## Form Architecture" in md


def test_markdown_includes_state_management():
    md = output_to_markdown(mock_frontend_architect_output())
    assert "## State Management Architecture" in md


def test_markdown_includes_development_guidelines():
    md = output_to_markdown(mock_frontend_architect_output())
    assert "## Frontend Development Guidelines" in md
