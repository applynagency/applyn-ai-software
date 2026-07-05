from app.schemas.fullstack_assembly import FullstackAssemblyOutput


def output_to_markdown(output: FullstackAssemblyOutput) -> str:
    """Convert structured Full Stack Assembly output to a readable markdown document."""
    lines: list[str] = [
        "# Full Stack Assembly Package",
        "",
        "## Summary",
        "",
        f"- **Assembly Status:** {output.assembly_status}",
        f"- **Assembler Version:** {output.release_metadata.get('assembler_version', '—')}",
        f"- **Backend Included:** {output.backend_package.get('included', False)}",
        "",
    ]

    manifest = output.application_manifest or {}
    if manifest:
        lines.extend(["## Application Manifest", ""])
        lines.append(f"- **Name:** {manifest.get('name', 'unknown')}")
        lines.append(f"- **Version:** {manifest.get('version', 'unknown')}")
        if manifest.get("description"):
            lines.append(f"- **Description:** {manifest['description']}")
        components = manifest.get("components") or {}
        if components:
            lines.append(
                f"- **Components:** frontend={components.get('frontend', {})}, "
                f"backend={components.get('backend', {})}"
            )
        lines.append("")

    if output.release_metadata:
        lines.extend(["## Release Metadata", ""])
        for key, value in output.release_metadata.items():
            lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")
        lines.append("")

    if output.environment_variables:
        lines.extend(["## Environment Variables", ""])
        for env in output.environment_variables:
            name = env.get("name", "UNKNOWN")
            desc = env.get("description", "")
            lines.append(f"- `{name}` — {desc}")
        lines.append("")

    if output.health_checks:
        lines.extend(["## Health Checks", ""])
        for component, config in output.health_checks.items():
            lines.append(f"- **{component}:** {config}")
        lines.append("")

    if output.startup_configuration:
        lines.extend(["## Startup Configuration", ""])
        order = output.startup_configuration.get("order") or []
        lines.append(f"- Startup order: {', '.join(order)}")
        for component in order:
            config = output.startup_configuration.get(component) or {}
            lines.append(f"- **{component}:** {config}")
        lines.append("")

    if output.docker_assets:
        lines.extend(["## Docker Assets", ""])
        compose = output.docker_assets.get("compose_file") or {}
        if compose.get("path"):
            lines.append(f"- Compose: `{compose['path']}`")
        docker_config = output.docker_assets.get("docker_configuration") or {}
        if docker_config:
            lines.append(f"- Frontend image: {(docker_config.get('frontend') or {}).get('base_image', '—')}")
            lines.append(f"- Backend image: {(docker_config.get('backend') or {}).get('base_image', '—')}")
        lines.append("")

    if output.deployment_assets:
        lines.extend(["## Deployment Assets", ""])
        for key in output.deployment_assets:
            lines.append(f"- {key}")
        lines.append("")

    if output.infrastructure_templates:
        lines.extend(["## Infrastructure Templates", ""])
        for key in output.infrastructure_templates:
            lines.append(f"- {key}")
        lines.append("")

    frontend = output.frontend_package or {}
    lines.extend([
        "## Frontend Package",
        "",
        f"- Files: {frontend.get('file_count', 0)}",
        f"- Build status: {(frontend.get('execution_summary') or {}).get('build_status', '—')}",
        "",
    ])

    backend = output.backend_package or {}
    lines.extend([
        "## Backend Package",
        "",
        f"- Included: {backend.get('included', False)}",
        f"- Files: {backend.get('file_count', 0)}",
        f"- Build status: {(backend.get('execution_summary') or {}).get('build_status', '—')}",
        "",
    ])

    if output.readme:
        lines.extend(["## README", "", output.readme.strip(), ""])

    return "\n".join(lines).strip() + "\n"
