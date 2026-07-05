from app.fullstack_assembly.markdown import output_to_markdown
from app.tests.conftest import mock_fullstack_assembly_output


def test_markdown_includes_deployment_assets_section():
    md = output_to_markdown(mock_fullstack_assembly_output())
    assert "## Deployment Assets" in md
    assert "kubernetes" in md


def test_markdown_includes_infrastructure_templates_section():
    md = output_to_markdown(mock_fullstack_assembly_output())
    assert "## Infrastructure Templates" in md
    assert "terraform" in md


def test_markdown_includes_health_checks_section():
    md = output_to_markdown(mock_fullstack_assembly_output())
    assert "## Health Checks" in md
    assert "frontend" in md


def test_markdown_includes_startup_configuration_section():
    md = output_to_markdown(mock_fullstack_assembly_output())
    assert "## Startup Configuration" in md
    assert "backend" in md


def test_markdown_includes_release_metadata_section():
    md = output_to_markdown(mock_fullstack_assembly_output())
    assert "## Release Metadata" in md
    assert "2.0.0" in md


def test_markdown_includes_readme_section():
    md = output_to_markdown(mock_fullstack_assembly_output())
    assert "## README" in md
    assert "Deployable Full-Stack Package" in md


def test_markdown_shows_backend_included_when_present():
    output = mock_fullstack_assembly_output(
        backend_package={
            "included": True,
            "execution_summary": {"build_status": "success"},
        }
    )
    md = output_to_markdown(output)
    assert "**Backend Included:** True" in md
    assert "Included: True" in md


def test_markdown_includes_manifest_components():
    md = output_to_markdown(mock_fullstack_assembly_output())
    assert "**Components:**" in md


def test_markdown_ends_with_trailing_newline():
    md = output_to_markdown(mock_fullstack_assembly_output())
    assert md.endswith("\n")
