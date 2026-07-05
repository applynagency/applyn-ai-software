from app.frontend_v1.markdown import output_to_markdown
from app.tests.conftest import mock_frontend_v1_output


def test_markdown_includes_development_conventions():
    md = output_to_markdown(mock_frontend_v1_output())
    assert "## Development Conventions" in md


def test_markdown_includes_folder_organization():
    md = output_to_markdown(mock_frontend_v1_output())
    assert "## Folder Organization" in md


def test_markdown_includes_api_client_structure():
    md = output_to_markdown(mock_frontend_v1_output())
    assert "## API Client Structure" in md


def test_markdown_includes_layout_structure():
    md = output_to_markdown(mock_frontend_v1_output())
    assert "## Layout Structure" in md


def test_markdown_lists_page_file_paths():
    md = output_to_markdown(mock_frontend_v1_output())
    assert "page.tsx" in md


def test_markdown_lists_component_file_paths():
    md = output_to_markdown(mock_frontend_v1_output())
    assert "components/ui" in md
