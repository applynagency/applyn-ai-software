from app.schemas.frontend_v1 import FrontendDeveloperV1Output


def output_to_markdown(output: FrontendDeveloperV1Output) -> str:
    """Convert structured Frontend Developer V1 output to a readable markdown document."""
    lines: list[str] = ["# Frontend Implementation Blueprint", ""]

    project = output.project_structure or {}
    if project:
        lines.extend(["## Project Structure", ""])
        for key, value in project.items():
            if isinstance(value, list):
                lines.append(f"**{key.replace('_', ' ').title()}:**")
                for item in value:
                    lines.append(f"- {item}")
            else:
                lines.append(f"**{key.replace('_', ' ').title()}:** {value}")
        lines.append("")

    if output.route_structure:
        lines.extend(["## Route Structure", ""])
        for route in output.route_structure:
            lines.append(
                f"- **{route.name}** ({route.id}): `{route.path}` → page {route.page_id or 'N/A'}"
            )
        lines.append("")

    if output.layout_structure:
        lines.extend(["## Layout Structure", ""])
        for layout in output.layout_structure:
            path = layout.file_path or "TBD"
            lines.append(f"- **{layout.name}** ({layout.id}): {layout.description} → `{path}`")
        lines.append("")

    if output.page_structure:
        lines.extend(["## Page Structure", ""])
        for page in output.page_structure:
            lines.append(
                f"- **{page.name}** ({page.id}): `{page.route}` → `{page.file_path}` — {page.purpose}"
            )
        lines.append("")

    if output.component_structure:
        lines.extend(["## Component Structure", ""])
        for component in output.component_structure:
            lines.append(
                f"- **{component.name}** ({component.id}) [{component.category}]: "
                f"`{component.file_path}` — {component.description}"
            )
        lines.append("")

    api = output.api_client_structure or {}
    if api:
        lines.extend(["## API Client Structure", ""])
        for key, value in api.items():
            if isinstance(value, list):
                lines.append(f"**{key.replace('_', ' ').title()}:**")
                for item in value:
                    if isinstance(item, dict):
                        lines.append(f"- {item.get('name', item)}")
                    else:
                        lines.append(f"- {item}")
            else:
                lines.append(f"**{key.replace('_', ' ').title()}:** {value}")
        lines.append("")

    sm = output.state_management or {}
    modules = sm.get("modules", []) if isinstance(sm, dict) else []
    if sm:
        lines.extend(["## State Management Structure", ""])
        if modules:
            for module in modules:
                if isinstance(module, dict):
                    lines.append(
                        f"- **{module.get('name', 'Module')}** ({module.get('id', 'N/A')}): "
                        f"{module.get('description', '')} [scope: {module.get('scope', 'N/A')}]"
                    )
        for key, value in sm.items():
            if key == "modules":
                continue
            if isinstance(value, list):
                lines.append(f"**{key.replace('_', ' ').title()}:**")
                for item in value:
                    lines.append(f"- {item}")
            else:
                lines.append(f"**{key.replace('_', ' ').title()}:** {value}")
        lines.append("")

    if output.form_architecture:
        lines.extend(["## Form Architecture", ""])
        for form in output.form_architecture:
            fields = ", ".join(form.fields) if form.fields else "none"
            lines.append(
                f"- **{form.name}** ({form.id}) on {form.page_id}: [{fields}] "
                f"(validation: {form.validation_approach or 'default'})"
            )
        lines.append("")

    vs = output.validation_strategy or {}
    if vs:
        lines.extend(["## Validation Strategy", ""])
        for key, value in vs.items():
            if isinstance(value, list):
                lines.append(f"**{key.replace('_', ' ').title()}:**")
                for item in value:
                    lines.append(f"- {item}")
            else:
                lines.append(f"**{key.replace('_', ' ').title()}:** {value}")
        lines.append("")

    folders = output.folder_organization or {}
    if folders:
        lines.extend(["## Folder Organization", ""])
        for key, value in folders.items():
            lines.append(f"- **{key}/**: {value}")
        lines.append("")

    if output.development_conventions:
        lines.extend(["## Development Conventions", ""])
        lines.extend(f"- {item}" for item in output.development_conventions)
        lines.append("")

    if output.module_breakdown:
        lines.extend(["## Frontend Module Breakdown", ""])
        for module in output.module_breakdown:
            pages = ", ".join(module.pages) if module.pages else "none"
            components = ", ".join(module.components) if module.components else "none"
            lines.append(
                f"- **{module.name}** ({module.id}): {module.description} "
                f"[pages: {pages}; components: {components}]"
            )
        lines.append("")

    return "\n".join(lines).strip() + "\n"
