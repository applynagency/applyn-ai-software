from app.schemas.deployment import DeploymentOutput


def output_to_markdown(output: DeploymentOutput) -> str:
    lines: list[str] = [
        "# Deployment Report",
        "",
        "## Summary",
        "",
        f"- **Provider:** {output.deployment_provider}",
        f"- **Status:** {output.deployment_status}",
        f"- **Live URL:** {output.live_url or '—'}",
        f"- **Rollback Available:** {output.rollback_available}",
        "",
    ]

    metadata = output.deployment_metadata or {}
    if metadata:
        lines.extend(["## Deployment Metadata", ""])
        for key, value in metadata.items():
            lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")
        lines.append("")

    if output.deployment_logs:
        lines.extend(["## Deployment Logs", ""])
        for entry in output.deployment_logs:
            if isinstance(entry, dict):
                lines.append(f"- {entry.get('message', entry)}")
            else:
                lines.append(f"- {entry}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"
