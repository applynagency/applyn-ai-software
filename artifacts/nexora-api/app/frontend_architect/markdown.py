from app.schemas.frontend_architect import FrontendArchitectOutput


def output_to_markdown(output: FrontendArchitectOutput) -> str:
    """Convert structured Frontend Architect output to a readable markdown document."""
    lines: list[str] = ["# Frontend Architecture Blueprint", ""]

    stack = output.frontend_stack or {}
    if stack:
        lines.extend(["## Frontend Technology Stack", ""])
        for key, value in stack.items():
            if isinstance(value, list):
                lines.append(f"**{key.replace('_', ' ').title()}:**")
                for item in value:
                    lines.append(f"- {item}")
            else:
                lines.append(f"**{key.replace('_', ' ').title()}:** {value}")
        lines.append("")

    if output.routing_architecture:
        lines.extend(["## Routing Architecture", ""])
        for route in output.routing_architecture:
            auth = "protected" if route.auth_required else "public"
            lines.append(
                f"- **{route.name}** ({route.id}): `{route.path}` → page {route.page_id or 'N/A'} "
                f"[{auth}]"
            )
        lines.append("")

    if output.page_architecture:
        lines.extend(["## Page Architecture", ""])
        for page in output.page_architecture:
            lines.append(
                f"- **{page.name}** ({page.id}): `{page.route}` — {page.purpose} "
                f"(layout: {page.layout_id or 'default'})"
            )
        lines.append("")

    if output.layout_architecture:
        lines.extend(["## Layout Architecture", ""])
        for layout in output.layout_architecture:
            regions = ", ".join(layout.regions) if layout.regions else "N/A"
            lines.append(f"- **{layout.name}** ({layout.id}): {layout.description} [regions: {regions}]")
        lines.append("")

    if output.component_architecture:
        lines.extend(["## Component Architecture", ""])
        for component in output.component_architecture:
            props = ", ".join(component.props) if component.props else "none"
            lines.append(
                f"- **{component.name}** ({component.id}) [{component.category}]: "
                f"{component.description} (props: {props})"
            )
        lines.append("")

    sm = output.state_management or {}
    if sm:
        lines.extend(["## State Management Architecture", ""])
        for key, value in sm.items():
            if isinstance(value, list):
                lines.append(f"**{key.replace('_', ' ').title()}:**")
                for item in value:
                    lines.append(f"- {item}")
            else:
                lines.append(f"**{key.replace('_', ' ').title()}:** {value}")
        lines.append("")

    api = output.api_integration or {}
    integrations = api.get("integrations", []) if isinstance(api, dict) else []
    if integrations:
        lines.extend(["## API Integration Architecture", ""])
        for item in integrations:
            method = item.get("method", "GET")
            path = item.get("path", "/")
            desc = item.get("description", "")
            lines.append(f"- `{method} {path}`: {desc}")
        lines.append("")

    auth = output.authentication or {}
    if auth:
        lines.extend(["## Authentication Architecture", ""])
        for key, value in auth.items():
            if isinstance(value, list):
                lines.append(f"**{key.replace('_', ' ').title()}:**")
                for item in value:
                    lines.append(f"- {item}")
            else:
                lines.append(f"**{key.replace('_', ' ').title()}:** {value}")
        lines.append("")

    if output.forms:
        lines.extend(["## Form Architecture", ""])
        for form in output.forms:
            fields = ", ".join(form.fields) if form.fields else "none"
            lines.append(
                f"- **{form.name}** ({form.id}) on {form.page_id}: fields [{fields}] "
                f"(validation: {form.validation_strategy or 'default'})"
            )
        lines.append("")

    ds = output.design_system_mapping or {}
    if ds:
        lines.extend(["## Design System Mapping", ""])
        for key, value in ds.items():
            if isinstance(value, list):
                lines.append(f"**{key.replace('_', ' ').title()}:**")
                for item in value:
                    lines.append(f"- {item}")
            else:
                lines.append(f"**{key.replace('_', ' ').title()}:** {value}")
        lines.append("")

    folders = output.folder_structure or {}
    if folders:
        lines.extend(["## Folder Structure", ""])
        for key, value in folders.items():
            lines.append(f"- **{key}/**: {value}")
        lines.append("")

    deploy = output.deployment_architecture or {}
    if deploy:
        lines.extend(["## Deployment Architecture", ""])
        for key, value in deploy.items():
            if isinstance(value, list):
                lines.append(f"**{key.replace('_', ' ').title()}:**")
                for item in value:
                    lines.append(f"- {item}")
            else:
                lines.append(f"**{key.replace('_', ' ').title()}:** {value}")
        lines.append("")

    if output.development_guidelines:
        lines.extend(["## Frontend Development Guidelines", ""])
        lines.extend(f"- {item}" for item in output.development_guidelines)
        lines.append("")

    return "\n".join(lines).strip() + "\n"
