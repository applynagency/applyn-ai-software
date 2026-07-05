from app.docker_agent.markdown import output_to_markdown
from app.tests.conftest import mock_docker_agent_output


def test_markdown_includes_title():
    md = output_to_markdown(mock_docker_agent_output())
    assert "# Docker Containerization Blueprint" in md


def test_markdown_includes_dockerfile_strategy():
    md = output_to_markdown(mock_docker_agent_output())
    assert "## Dockerfile Strategy" in md


def test_markdown_includes_docker_compose():
    md = output_to_markdown(mock_docker_agent_output())
    assert "## Docker Compose" in md


def test_markdown_includes_container_topology():
    md = output_to_markdown(mock_docker_agent_output())
    assert "## Container Topology" in md


def test_markdown_includes_security_hardening():
    md = output_to_markdown(mock_docker_agent_output())
    assert "## Security Hardening" in md
