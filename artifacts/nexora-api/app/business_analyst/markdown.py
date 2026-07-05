from app.schemas.business_analyst import BusinessAnalystOutput


def output_to_markdown(output: BusinessAnalystOutput) -> str:
    """Convert structured BA output to a readable markdown document."""
    lines: list[str] = ["# Business Analysis Document", ""]

    summary = output.project_summary or {}
    if summary:
        lines.extend(["## Project Summary", ""])
        for key, value in summary.items():
            if isinstance(value, list):
                lines.append(f"**{key.replace('_', ' ').title()}:**")
                for item in value:
                    lines.append(f"- {item}")
            else:
                lines.append(f"**{key.replace('_', ' ').title()}:** {value}")
        lines.append("")

    sections = [
        ("Functional Requirements", output.functional_requirements, lambda item: f"- **{item.id}** {item.title}: {item.description} (priority: {item.priority})"),
        ("Non-Functional Requirements", output.non_functional_requirements, lambda item: f"- **{item.id}** [{item.category}] {item.description}"),
        ("Roles", output.roles, lambda item: f"- **{item.name}**: {item.description}"),
        ("Permissions", output.permissions, lambda item: f"- **{item.role}** → {item.action} on {item.resource}: {item.description}"),
        ("Modules", output.modules, lambda item: f"- **{item.name}**: {item.description}"),
        ("Business Rules", output.business_rules, lambda item: f"- **{item.name}**: {item.description}"),
        ("Entities", output.entities, lambda item: f"- **{item.name}**: {item.description} (attributes: {', '.join(item.attributes)})"),
        ("User Flows", output.user_flows, lambda item: f"- **{item.name}** (actor: {item.actor}): {' → '.join(item.steps)}"),
        ("API Requirements", output.api_requirements, lambda item: f"- `{item.method} {item.path}`: {item.description}"),
        ("Acceptance Criteria", output.acceptance_criteria, lambda item: f"- **{item.id}** (ref: {item.requirement_id}): {item.description}"),
        ("Assumptions", output.assumptions, lambda item: f"- {item.description} (impact: {item.impact})"),
        ("Risks", output.risks, lambda item: f"- {item.description} (impact: {item.impact}, mitigation: {item.mitigation or 'N/A'})"),
        ("Dependencies", output.dependencies, lambda item: f"- **{item.name}** [{item.type}]: {item.description}"),
    ]

    for title, items, formatter in sections:
        if items:
            lines.extend([f"## {title}", ""])
            lines.extend(formatter(item) for item in items)
            lines.append("")

    return "\n".join(lines).strip() + "\n"
