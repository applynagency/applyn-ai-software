from app.kubernetes_agent.markdown import output_to_markdown
from app.tests.conftest import mock_kubernetes_agent_output


def test_markdown_includes_title():
    md = output_to_markdown(mock_kubernetes_agent_output())
    assert "# Kubernetes Manifest Plan" in md


def test_markdown_includes_deployments():
    md = output_to_markdown(mock_kubernetes_agent_output())
    assert "## Deployments" in md


def test_markdown_includes_services():
    md = output_to_markdown(mock_kubernetes_agent_output())
    assert "## Services" in md


def test_markdown_includes_ingress():
    md = output_to_markdown(mock_kubernetes_agent_output())
    assert "## Ingress" in md


def test_markdown_includes_hpas():
    md = output_to_markdown(mock_kubernetes_agent_output())
    assert "## Horizontal Pod Autoscalers" in md


def test_markdown_includes_configmaps_secrets():
    md = output_to_markdown(mock_kubernetes_agent_output())
    assert "## ConfigMaps & Secrets" in md


def test_markdown_includes_network_policies():
    md = output_to_markdown(mock_kubernetes_agent_output())
    assert "## Network Policies" in md


def test_markdown_includes_environment_overlays():
    md = output_to_markdown(mock_kubernetes_agent_output())
    assert "## Environment Overlays" in md


def test_markdown_handles_empty_output():
    from app.schemas.kubernetes_agent import KubernetesAgentOutput

    md = output_to_markdown(KubernetesAgentOutput())
    assert "_None defined_" in md
