from app.frontend_v2.markdown import output_to_markdown
from app.tests.conftest import mock_frontend_v2_output


def test_markdown_includes_provider_files():
    md = output_to_markdown(mock_frontend_v2_output())
    assert "## Provider Files" in md


def test_markdown_includes_middleware_files():
    md = output_to_markdown(mock_frontend_v2_output())
    assert "## Middleware Files" in md


def test_markdown_includes_utility_files():
    md = output_to_markdown(mock_frontend_v2_output())
    assert "## Utility Files" in md


def test_markdown_includes_form_files():
    md = output_to_markdown(mock_frontend_v2_output())
    assert "## Form Files" in md


def test_markdown_includes_validation_files():
    md = output_to_markdown(mock_frontend_v2_output())
    assert "## Validation Files" in md


def test_markdown_lists_tsx_file_paths():
    md = output_to_markdown(mock_frontend_v2_output())
    assert ".tsx" in md
