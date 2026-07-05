from app.schemas.backend_v3 import BackendDeveloperV3Output


def _language_for_path(path: str) -> str:
    if path.endswith(".py"):
        return "python"
    if path.endswith(".ini"):
        return "ini"
    if path.endswith(".md"):
        return "markdown"
    if path.endswith("Dockerfile"):
        return "dockerfile"
    if path.endswith(".txt"):
        return "text"
    if path.endswith(".yml") or path.endswith(".yaml"):
        return "yaml"
    return "text"


def output_to_markdown(output: BackendDeveloperV3Output) -> str:
    """Convert structured Backend Developer V3 output to a readable markdown document."""
    lines: list[str] = ["# Generated Backend Codebase", ""]

    structure = output.project_structure or {}
    if structure:
        lines.extend(["## Project Structure", ""])
        for key, value in structure.items():
            if isinstance(value, list):
                lines.append(f"**{key.replace('_', ' ').title()}:**")
                for item in value:
                    lines.append(f"- {item}")
            else:
                lines.append(f"**{key.replace('_', ' ').title()}:** {value}")
        lines.append("")

    if output.requirements_txt:
        lines.extend(["## Requirements", ""])
        lines.append("```text")
        lines.append(output.requirements_txt.strip())
        lines.append("```")
        lines.append("")

    if output.environment_variables:
        lines.extend(["## Environment Variables", ""])
        for env in output.environment_variables:
            name = env.get("name", "UNKNOWN")
            desc = env.get("description", "")
            lines.append(f"- `{name}` — {desc}")
        lines.append("")

    if output.docker_configuration:
        lines.extend(["## Docker Configuration", ""])
        for key, value in output.docker_configuration.items():
            lines.append(f"- **{key}:** {value}")
        lines.append("")

    if output.readme:
        lines.extend(["## README", "", output.readme.strip(), ""])

    lines.extend([
        f"## Generated Files ({len(output.generated_files)})",
        "",
    ])

    for file in output.generated_files[:20]:
        lang = _language_for_path(file.path)
        lines.append(f"### `{file.path}`")
        lines.append("")
        lines.append(f"```{lang}")
        preview = file.content[:2000]
        if len(file.content) > 2000:
            preview += "\n... (truncated)"
        lines.append(preview)
        lines.append("```")
        lines.append("")

    if len(output.generated_files) > 20:
        lines.append(f"_Showing 20 of {len(output.generated_files)} files._")
        lines.append("")

    return "\n".join(lines).strip() + "\n"
