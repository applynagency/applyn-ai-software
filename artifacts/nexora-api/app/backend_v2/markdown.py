from app.schemas.backend_v2 import BackendDeveloperV2Output


def _format_file_section(title: str, files: list) -> list[str]:
    lines: list[str] = [f"## {title}", ""]
    if not files:
        lines.append("_None specified._")
        lines.append("")
        return lines
    for item in files:
        deps = ", ".join(item.dependencies) if item.dependencies else "none"
        exports = ", ".join(item.exports) if item.exports else "default"
        lines.append(f"- **{item.name}** ({item.id})")
        lines.append(f"  - Path: `{item.path}`")
        lines.append(f"  - Description: {item.description}")
        if item.purpose:
            lines.append(f"  - Purpose: {item.purpose}")
        lines.append(f"  - Exports: {exports}")
        lines.append(f"  - Dependencies: {deps}")
    lines.append("")
    return lines


def output_to_markdown(output: BackendDeveloperV2Output) -> str:
    """Convert structured Backend Developer V2 output to a readable markdown document."""
    lines: list[str] = ["# Backend File-Level Specifications", ""]

    structure = output.file_structure or {}
    if structure:
        lines.extend(["## File Structure", ""])
        for key, value in structure.items():
            if isinstance(value, list):
                lines.append(f"**{key.replace('_', ' ').title()}:**")
                for item in value:
                    lines.append(f"- {item}")
            else:
                lines.append(f"**{key.replace('_', ' ').title()}:** {value}")
        lines.append("")

    sections = [
        ("Router Files", output.router_files),
        ("Schema Files", output.schema_files),
        ("Model Files", output.model_files),
        ("Repository Files", output.repository_files),
        ("Service Files", output.service_files),
        ("Dependency Files", output.dependency_files),
        ("Middleware Files", output.middleware_files),
        ("Background Job Files", output.background_job_files),
        ("Integration Files", output.integration_files),
        ("Configuration Files", output.configuration_files),
        ("Migration Files", output.migration_files),
        ("Test Files", output.test_files),
        ("Infrastructure Files", output.infrastructure_files),
    ]

    for title, files in sections:
        lines.extend(_format_file_section(title, files))

    return "\n".join(lines).strip() + "\n"
