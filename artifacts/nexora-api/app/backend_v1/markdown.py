from app.schemas.backend_v1 import BackendDeveloperV1Output


def output_to_markdown(output: BackendDeveloperV1Output) -> str:
    """Convert structured Backend Developer V1 output to a readable markdown document."""
    lines: list[str] = ["# Backend Implementation Specification", ""]

    if output.service_specifications:
        lines.extend(["## Service Specifications", ""])
        for service in output.service_specifications:
            lines.append(
                f"- **{service.name}** ({service.id}): {service.description}"
            )
        lines.append("")

    if output.repository_specifications:
        lines.extend(["## Repository Specifications", ""])
        for repo in output.repository_specifications:
            entity = repo.entity or "N/A"
            lines.append(
                f"- **{repo.name}** ({repo.id}) [entity: {entity}]: {repo.description}"
            )
        lines.append("")

    if output.api_specifications:
        lines.extend(["## API Specifications", ""])
        for api in output.api_specifications:
            lines.append(
                f"- `{api.method} {api.path}` ({api.id}): {api.description}"
            )
        lines.append("")

    if output.database_model_specifications:
        lines.extend(["## Database Model Specifications", ""])
        for model in output.database_model_specifications:
            table = model.table_name or "TBD"
            lines.append(
                f"- **{model.name}** ({model.id}) [table: {table}]: {model.description}"
            )
        lines.append("")

    auth = output.authentication_specifications
    if auth.strategy or auth.token_type or auth.providers:
        lines.extend(["## Authentication Specifications", ""])
        if auth.strategy:
            lines.append(f"**Strategy:** {auth.strategy}")
        if auth.token_type:
            lines.append(f"**Token Type:** {auth.token_type}")
        if auth.providers:
            lines.append("**Providers:**")
            lines.extend(f"- {provider}" for provider in auth.providers)
        if auth.middleware:
            lines.append("**Middleware:**")
            lines.extend(f"- {item}" for item in auth.middleware)
        lines.append("")

    authz = output.authorization_specifications
    if authz.roles or authz.policies:
        lines.extend(["## Authorization Specifications", ""])
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

    if output.validation_specifications:
        lines.extend(["## Validation Specifications", ""])
        for spec in output.validation_specifications:
            lines.append(
                f"- **{spec.name}** ({spec.id}) [{spec.scope or 'N/A'}]: {spec.description}"
            )
        lines.append("")

    if output.background_job_specifications:
        lines.extend(["## Background Job Specifications", ""])
        for job in output.background_job_specifications:
            lines.append(
                f"- **{job.name}** ({job.id}) [queue: {job.queue or 'default'}]: {job.description}"
            )
        lines.append("")

    if output.integration_specifications:
        lines.extend(["## Integration Specifications", ""])
        for integration in output.integration_specifications:
            lines.append(
                f"- **{integration.name}** [{integration.type}] ({integration.id}): {integration.description}"
            )
        lines.append("")

    if output.folder_structure:
        lines.extend(["## Folder Structure", ""])
        for key, value in output.folder_structure.items():
            lines.append(f"- **{key}/**: {value}")
        lines.append("")

    if output.module_breakdown:
        lines.extend(["## Module Breakdown", ""])
        for module in output.module_breakdown:
            services = ", ".join(module.services) if module.services else "none"
            repos = ", ".join(module.repositories) if module.repositories else "none"
            lines.append(
                f"- **{module.name}** ({module.id}): {module.description} "
                f"[services: {services}; repositories: {repos}]"
            )
        lines.append("")

    if output.implementation_guidelines:
        lines.extend(["## Implementation Guidelines", ""])
        lines.extend(f"- {item}" for item in output.implementation_guidelines)
        lines.append("")

    return "\n".join(lines).strip() + "\n"
