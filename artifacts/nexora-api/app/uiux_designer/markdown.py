from app.schemas.uiux_designer import UIUXDesignerOutput


def output_to_markdown(output: UIUXDesignerOutput) -> str:
    """Convert structured UI/UX output to a readable markdown document."""
    lines: list[str] = ["# UI/UX Design Specification", ""]

    ia = output.information_architecture or {}
    if ia:
        lines.extend(["## Information Architecture", ""])
        for key, value in ia.items():
            if isinstance(value, list):
                lines.append(f"**{key.replace('_', ' ').title()}:**")
                for item in value:
                    lines.append(f"- {item}")
            else:
                lines.append(f"**{key.replace('_', ' ').title()}:** {value}")
        lines.append("")

    if output.navigation_structure:
        lines.extend(["## Navigation Structure", ""])
        for group in output.navigation_structure:
            lines.append(f"### {group.name} ({group.id})")
            lines.append(group.description)
            for item in group.items:
                lines.append(f"- {item}")
            lines.append("")

    if output.user_flows:
        lines.extend(["## User Flows", ""])
        for flow in output.user_flows:
            screens = ", ".join(flow.screens) if flow.screens else "N/A"
            lines.append(
                f"- **{flow.name}** ({flow.id}) — actor: {flow.actor}; screens: {screens}"
            )
            for step in flow.steps:
                lines.append(f"  1. {step}")
        lines.append("")

    if output.screen_inventory:
        lines.extend(["## Screen Inventory", ""])
        for screen in output.screen_inventory:
            actions = ", ".join(screen.primary_actions) if screen.primary_actions else "N/A"
            layout = screen.layout_type or "standard"
            lines.append(
                f"- **{screen.name}** ({screen.id}): {screen.purpose} "
                f"[layout: {layout}; actions: {actions}]"
            )
        lines.append("")

    if output.page_hierarchy:
        lines.extend(["## Page Hierarchy", ""])
        for page in output.page_hierarchy:
            parent = page.parent_id or "root"
            lines.append(f"- **{page.name}** ({page.id}) — level {page.level}, parent: {parent}")
        lines.append("")

    if output.role_screen_mapping:
        lines.extend(["## Role-Based Screen Mapping", ""])
        for mapping in output.role_screen_mapping:
            screens = ", ".join(mapping.screens)
            lines.append(f"- **{mapping.role}**: {screens}")
            if mapping.description:
                lines.append(f"  - {mapping.description}")
        lines.append("")

    ds = output.design_system or {}
    if ds:
        lines.extend(["## Design System Recommendations", ""])
        for key, value in ds.items():
            if isinstance(value, list):
                lines.append(f"**{key.replace('_', ' ').title()}:**")
                for item in value:
                    lines.append(f"- {item}")
            elif isinstance(value, dict):
                lines.append(f"**{key.replace('_', ' ').title()}:**")
                for sub_key, sub_value in value.items():
                    lines.append(f"- {sub_key}: {sub_value}")
            else:
                lines.append(f"**{key.replace('_', ' ').title()}:** {value}")
        lines.append("")

    if output.component_inventory:
        lines.extend(["## Component Inventory", ""])
        for component in output.component_inventory:
            usage = component.usage or "General use"
            lines.append(
                f"- **{component.name}** ({component.id}) [{component.category}]: "
                f"{component.description} — {usage}"
            )
        lines.append("")

    handoff = output.frontend_handoff or {}
    if handoff:
        lines.extend(["## Frontend Handoff Specification", ""])
        for key, value in handoff.items():
            if isinstance(value, list):
                lines.append(f"**{key.replace('_', ' ').title()}:**")
                for item in value:
                    lines.append(f"- {item}")
            else:
                lines.append(f"**{key.replace('_', ' ').title()}:** {value}")
        lines.append("")

    if output.responsive_guidelines:
        lines.extend(["## Responsive Design Guidelines", ""])
        lines.extend(f"- {item}" for item in output.responsive_guidelines)
        lines.append("")

    if output.accessibility_guidelines:
        lines.extend(["## Accessibility Guidelines", ""])
        lines.extend(f"- {item}" for item in output.accessibility_guidelines)
        lines.append("")

    return "\n".join(lines).strip() + "\n"
