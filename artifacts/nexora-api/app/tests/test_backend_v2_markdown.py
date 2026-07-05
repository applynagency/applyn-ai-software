from app.backend_v2.markdown import output_to_markdown
from app.tests.conftest import mock_backend_v2_output


def test_markdown_includes_title():
    md = output_to_markdown(mock_backend_v2_output())
    assert "# Backend File-Level Specifications" in md


def test_markdown_includes_file_structure():
    md = output_to_markdown(mock_backend_v2_output())
    assert "## File Structure" in md


def test_markdown_includes_router_files():
    md = output_to_markdown(mock_backend_v2_output())
    assert "## Router Files" in md


def test_markdown_includes_schema_files():
    md = output_to_markdown(mock_backend_v2_output())
    assert "## Schema Files" in md


def test_markdown_includes_model_files():
    md = output_to_markdown(mock_backend_v2_output())
    assert "## Model Files" in md


def test_markdown_includes_repository_files():
    md = output_to_markdown(mock_backend_v2_output())
    assert "## Repository Files" in md


def test_markdown_includes_service_files():
    md = output_to_markdown(mock_backend_v2_output())
    assert "## Service Files" in md


def test_markdown_includes_dependency_files():
    md = output_to_markdown(mock_backend_v2_output())
    assert "## Dependency Files" in md


def test_markdown_includes_middleware_files():
    md = output_to_markdown(mock_backend_v2_output())
    assert "## Middleware Files" in md


def test_markdown_includes_background_job_files():
    md = output_to_markdown(mock_backend_v2_output())
    assert "## Background Job Files" in md


def test_markdown_includes_integration_files():
    md = output_to_markdown(mock_backend_v2_output())
    assert "## Integration Files" in md


def test_markdown_includes_configuration_files():
    md = output_to_markdown(mock_backend_v2_output())
    assert "## Configuration Files" in md


def test_markdown_includes_migration_files():
    md = output_to_markdown(mock_backend_v2_output())
    assert "## Migration Files" in md


def test_markdown_includes_test_files():
    md = output_to_markdown(mock_backend_v2_output())
    assert "## Test Files" in md


def test_markdown_includes_infrastructure_files():
    md = output_to_markdown(mock_backend_v2_output())
    assert "## Infrastructure Files" in md


def test_markdown_lists_file_paths():
    md = output_to_markdown(mock_backend_v2_output())
    assert "`app/" in md


def test_markdown_lists_file_names():
    md = output_to_markdown(mock_backend_v2_output())
    assert "Item1" in md


def test_markdown_lists_exports_and_dependencies():
    md = output_to_markdown(mock_backend_v2_output())
    assert "Exports:" in md
    assert "Dependencies:" in md
