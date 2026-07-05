from app.frontend_v2.markdown import output_to_markdown
from app.tests.conftest import mock_frontend_v2_output


def test_markdown_includes_title():
    md = output_to_markdown(mock_frontend_v2_output())
    assert "# Frontend File-Level Specifications" in md


def test_markdown_includes_file_structure():
    md = output_to_markdown(mock_frontend_v2_output())
    assert "## File Structure" in md


def test_markdown_includes_page_files():
    md = output_to_markdown(mock_frontend_v2_output())
    assert "## Page Files" in md


def test_markdown_includes_component_files():
    md = output_to_markdown(mock_frontend_v2_output())
    assert "## Component Files" in md


def test_markdown_includes_layout_files():
    md = output_to_markdown(mock_frontend_v2_output())
    assert "## Layout Files" in md


def test_markdown_includes_service_files():
    md = output_to_markdown(mock_frontend_v2_output())
    assert "## API Service Files" in md


def test_markdown_includes_store_files():
    md = output_to_markdown(mock_frontend_v2_output())
    assert "## Store Files" in md


def test_markdown_includes_hook_files():
    md = output_to_markdown(mock_frontend_v2_output())
    assert "## Hook Files" in md


def test_markdown_includes_type_files():
    md = output_to_markdown(mock_frontend_v2_output())
    assert "## Type Files" in md
