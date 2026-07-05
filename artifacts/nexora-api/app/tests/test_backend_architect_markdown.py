from app.backend_architect.markdown import output_to_markdown
from app.tests.conftest import mock_backend_architect_output


def test_markdown_includes_title():
    md = output_to_markdown(mock_backend_architect_output())
    assert "# Backend Architecture Blueprint" in md


def test_markdown_includes_backend_stack():
    md = output_to_markdown(mock_backend_architect_output())
    assert "## Backend Stack" in md


def test_markdown_includes_service_architecture():
    md = output_to_markdown(mock_backend_architect_output())
    assert "## Service Architecture" in md


def test_markdown_includes_api_architecture():
    md = output_to_markdown(mock_backend_architect_output())
    assert "## API Architecture" in md


def test_markdown_includes_database_architecture():
    md = output_to_markdown(mock_backend_architect_output())
    assert "## Database Architecture" in md


def test_markdown_includes_integration_architecture():
    md = output_to_markdown(mock_backend_architect_output())
    assert "## Integration Architecture" in md


def test_markdown_includes_authorization_architecture():
    md = output_to_markdown(mock_backend_architect_output())
    assert "## Authorization Architecture" in md


def test_markdown_includes_security_architecture():
    md = output_to_markdown(mock_backend_architect_output())
    assert "## Security Architecture" in md


def test_markdown_includes_development_guidelines():
    md = output_to_markdown(mock_backend_architect_output())
    assert "## Development Guidelines" in md
