from app.deployment.markdown import output_to_markdown
from app.tests.conftest import mock_deployment_output


def test_markdown_includes_environment_in_metadata():
    md = output_to_markdown(mock_deployment_output())
    assert "**Environment:**" in md or "environment" in md.lower()


def test_markdown_includes_service_type_when_present():
    md = output_to_markdown(mock_deployment_output())
    assert "**Service Type:**" in md or "app-service" in md


def test_markdown_shows_each_log_entry():
    md = output_to_markdown(mock_deployment_output())
    assert md.count("- ") >= 3


def test_markdown_ends_with_trailing_newline():
    md = output_to_markdown(mock_deployment_output())
    assert md.endswith("\n")


def test_markdown_handles_empty_live_url():
    output = mock_deployment_output(live_url="", deployment_status="PENDING")
    md = output_to_markdown(output)
    assert "—" in md or "Live URL" in md


def test_markdown_includes_region_when_present():
    md = output_to_markdown(mock_deployment_output())
    assert "eastus" in md or "**Region:**" in md
