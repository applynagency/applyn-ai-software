from app.infrastructure_architect.markdown import output_to_markdown
from app.tests.conftest import mock_infrastructure_architect_output


def test_markdown_includes_title():
    md = output_to_markdown(mock_infrastructure_architect_output())
    assert "# Infrastructure Architecture Blueprint" in md


def test_markdown_includes_cloud_architecture():
    md = output_to_markdown(mock_infrastructure_architect_output())
    assert "## Cloud Architecture" in md


def test_markdown_includes_network_topology():
    md = output_to_markdown(mock_infrastructure_architect_output())
    assert "## Network Topology" in md


def test_markdown_includes_environments():
    md = output_to_markdown(mock_infrastructure_architect_output())
    assert "## Environments" in md


def test_markdown_includes_security_controls():
    md = output_to_markdown(mock_infrastructure_architect_output())
    assert "## Security Controls" in md
