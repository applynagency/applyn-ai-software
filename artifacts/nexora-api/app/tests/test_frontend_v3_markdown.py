from app.frontend_v3.markdown import output_to_markdown
from app.tests.conftest import mock_frontend_v3_output


def test_markdown_includes_title():
    md = output_to_markdown(mock_frontend_v3_output())
    assert "# Generated Frontend Codebase" in md


def test_markdown_includes_project_structure():
    md = output_to_markdown(mock_frontend_v3_output())
    assert "## Project Structure" in md


def test_markdown_includes_package_configuration():
    md = output_to_markdown(mock_frontend_v3_output())
    assert "## Package Configuration" in md


def test_markdown_includes_environment_variables():
    md = output_to_markdown(mock_frontend_v3_output())
    assert "## Environment Variables" in md


def test_markdown_includes_docker_configuration():
    md = output_to_markdown(mock_frontend_v3_output())
    assert "## Docker Configuration" in md


def test_markdown_includes_readme():
    md = output_to_markdown(mock_frontend_v3_output())
    assert "## README" in md


def test_markdown_includes_generated_files_section():
    md = output_to_markdown(mock_frontend_v3_output())
    assert "## Generated Files" in md


def test_markdown_includes_file_code_blocks():
    md = output_to_markdown(mock_frontend_v3_output())
    assert "```tsx" in md or "```typescript" in md
    assert "package.json" in md
