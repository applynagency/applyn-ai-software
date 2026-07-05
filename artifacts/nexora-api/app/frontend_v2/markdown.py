from app.schemas.frontend_v2 import FrontendDeveloperV2Output


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


def output_to_markdown(output: FrontendDeveloperV2Output) -> str:
    """Convert structured Frontend Developer V2 output to a readable markdown document."""
    lines: list[str] = ["# Frontend File-Level Specifications", ""]

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
        ("Page Files", output.page_files),
        ("Component Files", output.component_files),
        ("Layout Files", output.layout_files),
        ("API Service Files", output.service_files),
        ("Store Files", output.store_files),
        ("Hook Files", output.hook_files),
        ("Provider Files", output.provider_files),
        ("Type Files", output.type_files),
        ("Middleware Files", output.middleware_files),
        ("Utility Files", output.utility_files),
        ("Form Files", output.form_files),
        ("Validation Files", output.validation_files),
    ]

    for title, files in sections:
        lines.extend(_format_file_section(title, files))

    return "\n".join(lines).strip() + "\n"
