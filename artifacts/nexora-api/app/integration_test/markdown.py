from app.schemas.integration_test import IntegrationTestOutput


def output_to_markdown(output: IntegrationTestOutput) -> str:
    lines = ["# Integration Test Plan", ""]

    if output.api_test_cases:
        lines.extend(["## API Test Cases", ""])
        lines.extend(f"- **{item.name}** ({item.id}): {item.description}" for item in output.api_test_cases)
        lines.append("")

    if output.frontend_backend_flows:
        lines.extend(["## Frontend/Backend Flows", ""])
        lines.extend(
            f"- **{item.name}** ({item.id}): {item.description}"
            for item in output.frontend_backend_flows
        )
        lines.append("")

    if output.database_validation:
        lines.extend(["## Database Validation", ""])
        lines.extend(
            f"- **{item.name}** ({item.id}): {item.description}" for item in output.database_validation
        )
        lines.append("")

    if output.integration_coverage:
        lines.extend(["## Integration Coverage", "", str(output.integration_coverage), ""])

    return "\n".join(lines)
