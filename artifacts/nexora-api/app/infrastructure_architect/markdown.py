from app.schemas.infrastructure_architect import InfrastructureArchitectOutput


def output_to_markdown(output: InfrastructureArchitectOutput) -> str:
    lines = [
        "# Infrastructure Architecture Blueprint",
        "",
        "## Cloud Architecture",
        "",
        output.cloud_architecture,
        "",
        "## Network Topology",
        "",
        output.network_topology,
        "",
        "## Environment Design",
        "",
        output.environment_design,
        "",
        "## Scaling Strategy",
        "",
        output.scaling_strategy,
        "",
        "## High Availability Strategy",
        "",
        output.ha_strategy,
        "",
        "## Disaster Recovery",
        "",
        output.disaster_recovery,
        "",
    ]

    list_sections = [
        ("Environments", output.environments, lambda i: f"- **{i.name}** ({i.id}): {i.description}"),
        ("Scaling Rules", output.scaling_rules, lambda i: f"- **{i.name}** ({i.id}): {i.description}"),
        (
            "Security Controls",
            output.security_controls,
            lambda i: f"- **{i.name}** ({i.id}): {i.description}",
        ),
        (
            "Backup & Recovery Plans",
            output.backup_recovery_plans,
            lambda i: f"- **{i.name}** ({i.id}): {i.description}",
        ),
    ]

    for title, items, formatter in list_sections:
        if items:
            lines.extend([f"## {title}", ""])
            lines.extend(formatter(item) for item in items)
            lines.append("")

    return "\n".join(lines)
