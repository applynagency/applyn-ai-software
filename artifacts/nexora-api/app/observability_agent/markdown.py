from app.schemas.observability_agent import ObservabilityAgentOutput


def output_to_markdown(output: ObservabilityAgentOutput) -> str:
    lines = ["# Observability Blueprint", ""]

    text_sections = [
        ("Prometheus Configuration", output.prometheus_configuration),
        ("Logging Architecture", output.logging_architecture),
        ("Tracing Architecture", output.tracing_architecture),
    ]
    for title, content in text_sections:
        lines.extend([f"## {title}", "", content or "_Not provided_", ""])

    list_sections = [
        ("Grafana Dashboards", output.grafana_dashboards),
        ("Alert Rules", output.alert_rules),
        ("Logging Flows", output.logging_flows),
        ("SLI/SLO Definitions", output.slo_definitions),
    ]
    for title, items in list_sections:
        lines.extend([f"## {title}", ""])
        if items:
            for item in items:
                lines.append(f"- **{item.name}**: {item.description}")
        else:
            lines.append("- _None defined_")
        lines.append("")

    return "\n".join(lines)
