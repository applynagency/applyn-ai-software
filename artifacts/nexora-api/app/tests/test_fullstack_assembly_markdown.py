from app.fullstack_assembly.markdown import output_to_markdown
from app.tests.conftest import mock_fullstack_assembly_output


def test_markdown_includes_title():
    md = output_to_markdown(mock_fullstack_assembly_output())
    assert "# Full Stack Assembly Package" in md


def test_markdown_includes_assembly_status():
    md = output_to_markdown(mock_fullstack_assembly_output())
    assert "**Assembly Status:**" in md
    assert "ASSEMBLY_APPROVED" in md


def test_markdown_includes_backend_included_flag():
    md = output_to_markdown(mock_fullstack_assembly_output())
    assert "**Backend Included:**" in md
    assert "True" in md


def test_markdown_includes_summary_section():
    md = output_to_markdown(mock_fullstack_assembly_output())
    assert "## Summary" in md


def test_markdown_includes_application_manifest_section():
    md = output_to_markdown(mock_fullstack_assembly_output())
    assert "## Application Manifest" in md
    assert "generated-app" in md


def test_markdown_includes_environment_variables_section():
    md = output_to_markdown(mock_fullstack_assembly_output())
    assert "## Environment Variables" in md
    assert "NEXT_PUBLIC_API_URL" in md


def test_markdown_includes_docker_assets_section():
    md = output_to_markdown(mock_fullstack_assembly_output())
    assert "## Docker Assets" in md
    assert "docker-compose.yml" in md


def test_markdown_includes_frontend_and_backend_package_sections():
    md = output_to_markdown(mock_fullstack_assembly_output())
    assert "## Frontend Package" in md
    assert "## Backend Package" in md
    assert "Included: True" in md
