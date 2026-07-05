from app.backend_v1.markdown import output_to_markdown
from app.tests.conftest import mock_backend_v1_output


def test_markdown_includes_title():
    md = output_to_markdown(mock_backend_v1_output())
    assert "# Backend Implementation Specification" in md


def test_markdown_includes_service_specifications():
    md = output_to_markdown(mock_backend_v1_output())
    assert "## Service Specifications" in md


def test_markdown_includes_repository_specifications():
    md = output_to_markdown(mock_backend_v1_output())
    assert "## Repository Specifications" in md


def test_markdown_includes_api_specifications():
    md = output_to_markdown(mock_backend_v1_output())
    assert "## API Specifications" in md


def test_markdown_includes_database_model_specifications():
    md = output_to_markdown(mock_backend_v1_output())
    assert "## Database Model Specifications" in md


def test_markdown_includes_authentication_specifications():
    md = output_to_markdown(mock_backend_v1_output())
    assert "## Authentication Specifications" in md
    assert "JWT" in md


def test_markdown_includes_authorization_specifications():
    md = output_to_markdown(mock_backend_v1_output())
    assert "## Authorization Specifications" in md
    assert "RBAC" in md


def test_markdown_includes_validation_specifications():
    md = output_to_markdown(mock_backend_v1_output())
    assert "## Validation Specifications" in md


def test_markdown_includes_background_job_specifications():
    md = output_to_markdown(mock_backend_v1_output())
    assert "## Background Job Specifications" in md


def test_markdown_includes_integration_specifications():
    md = output_to_markdown(mock_backend_v1_output())
    assert "## Integration Specifications" in md


def test_markdown_includes_folder_structure():
    md = output_to_markdown(mock_backend_v1_output())
    assert "## Folder Structure" in md


def test_markdown_includes_module_breakdown():
    md = output_to_markdown(mock_backend_v1_output())
    assert "## Module Breakdown" in md


def test_markdown_includes_implementation_guidelines():
    md = output_to_markdown(mock_backend_v1_output())
    assert "## Implementation Guidelines" in md


def test_markdown_lists_api_methods_and_paths():
    md = output_to_markdown(mock_backend_v1_output())
    assert "`GET /v1/resource-1`" in md or "`POST /v1/resource-2`" in md


def test_markdown_lists_service_names():
    md = output_to_markdown(mock_backend_v1_output())
    assert "Service1" in md
