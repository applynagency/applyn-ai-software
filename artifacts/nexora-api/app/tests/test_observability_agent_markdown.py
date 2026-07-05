from app.observability_agent.markdown import output_to_markdown
from app.schemas.observability_agent import ObservabilityAgentOutput
from app.tests.conftest import mock_observability_agent_output


def test_markdown_includes_title():
    md = output_to_markdown(mock_observability_agent_output())
    assert "# Observability Blueprint" in md


def test_markdown_includes_prometheus():
    md = output_to_markdown(mock_observability_agent_output())
    assert "## Prometheus Configuration" in md


def test_markdown_includes_logging_architecture():
    md = output_to_markdown(mock_observability_agent_output())
    assert "## Logging Architecture" in md


def test_markdown_includes_tracing_architecture():
    md = output_to_markdown(mock_observability_agent_output())
    assert "## Tracing Architecture" in md


def test_markdown_includes_dashboards():
    md = output_to_markdown(mock_observability_agent_output())
    assert "## Grafana Dashboards" in md


def test_markdown_includes_alert_rules():
    md = output_to_markdown(mock_observability_agent_output())
    assert "## Alert Rules" in md


def test_markdown_includes_logging_flows():
    md = output_to_markdown(mock_observability_agent_output())
    assert "## Logging Flows" in md


def test_markdown_includes_slo_definitions():
    md = output_to_markdown(mock_observability_agent_output())
    assert "## SLI/SLO Definitions" in md


def test_markdown_handles_empty_output():
    md = output_to_markdown(ObservabilityAgentOutput())
    assert "_None defined_" in md
