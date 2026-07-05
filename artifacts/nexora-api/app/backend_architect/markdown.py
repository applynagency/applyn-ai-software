from app.schemas.backend_architect import BackendArchitectOutput


def output_to_markdown(output: BackendArchitectOutput) -> str:
    """Convert structured Backend Architect output to a readable markdown document."""
    lines: list[str] = ["# Backend Architecture Blueprint", ""]

    if output.backend_stack:
        lines.extend(["## Backend Stack", ""])
        for key, value in output.backend_stack.items():
            lines.append(f"**{key.replace('_', ' ').title()}:** {value}")
        lines.append("")

    sections: list[tuple[str, list, callable]] = [
        (
            "Service Architecture",
            output.service_architecture,
            lambda item: f"- **{item.name}** ({item.id}): {item.description}",
        ),
        (
            "API Architecture",
            output.api_architecture,
            lambda item: f"- `{item.method} {item.path}` ({item.id}): {item.description}",
        ),
        (
            "Database Architecture",
            output.database_architecture,
            lambda item: f"- **{item.name}** ({item.id}): {item.description}",
        ),
        (
            "Integration Architecture",
            output.integration_architecture,
            lambda item: f"- **{item.name}** [{item.type}] ({item.id}): {item.description}",
        ),
    ]

    for title, items, formatter in sections:
        if items:
            lines.extend([f"## {title}", ""])
            lines.extend(formatter(item) for item in items)
            lines.append("")

    auth = output.authentication_architecture
    if auth.strategy or auth.token_type or auth.providers:
        lines.extend(["## Authentication Architecture", ""])
        if auth.strategy:
            lines.append(f"**Strategy:** {auth.strategy}")
        if auth.token_type:
            lines.append(f"**Token Type:** {auth.token_type}")
        if auth.providers:
            lines.append("**Providers:**")
            lines.extend(f"- {provider}" for provider in auth.providers)
        if auth.session_management:
            lines.append(f"**Session Management:** {auth.session_management}")
        lines.append("")

    authz = output.authorization_architecture
    if authz.roles or authz.policies:
        lines.extend(["## Authorization Architecture", ""])
        if authz.model:
            lines.append(f"**Model:** {authz.model}")
        if authz.roles:
            lines.append("**Roles:**")
            for role in authz.roles:
                lines.append(f"- **{role.name}** ({role.id}): {role.description}")
        if authz.policies:
            lines.append("**Policies:**")
            lines.extend(f"- {policy}" for policy in authz.policies)
        lines.append("")

    sec = output.security_architecture
    if sec.controls or sec.compliance or sec.threat_mitigations:
        lines.extend(["## Security Architecture", ""])
        if sec.controls:
            lines.append("**Controls:**")
            for control in sec.controls:
                lines.append(f"- **{control.name}** ({control.id}): {control.description}")
        if sec.compliance:
            lines.append("**Compliance:**")
            lines.extend(f"- {item}" for item in sec.compliance)
        if sec.threat_mitigations:
            lines.append("**Threat Mitigations:**")
            lines.extend(f"- {item}" for item in sec.threat_mitigations)
        lines.append("")

    dict_sections = [
        ("Caching Architecture", output.caching_architecture),
        ("Event Architecture", output.event_architecture),
        ("Deployment Architecture", output.deployment_architecture),
        ("Folder Structure", output.folder_structure),
    ]
    for title, data in dict_sections:
        if data:
            lines.extend([f"## {title}", ""])
            for key, value in data.items():
                if isinstance(value, list):
                    lines.append(f"**{key.replace('_', ' ').title()}:**")
                    lines.extend(f"- {item}" for item in value)
                else:
                    lines.append(f"**{key.replace('_', ' ').title()}:** {value}")
            lines.append("")

    if output.development_guidelines:
        lines.extend(["## Development Guidelines", ""])
        lines.extend(f"- {item}" for item in output.development_guidelines)
        lines.append("")

    return "\n".join(lines).strip() + "\n"
