from app.schemas.unit_test import UnitTestGeneratorOutput


def output_to_markdown(output: UnitTestGeneratorOutput) -> str:
    lines = ["# Unit Test Specifications", ""]

    if output.frontend_unit_test_specifications:
        lines.extend(["## Frontend Unit Tests", ""])
        lines.extend(
            f"- **{item.name}** ({item.id}): {item.description}"
            for item in output.frontend_unit_test_specifications
        )
        lines.append("")

    if output.backend_unit_test_specifications:
        lines.extend(["## Backend Unit Tests", ""])
        lines.extend(
            f"- **{item.name}** ({item.id}): {item.description}"
            for item in output.backend_unit_test_specifications
        )
        lines.append("")

    if output.test_fixtures:
        lines.extend(["## Test Fixtures", ""])
        lines.extend(f"- **{item.name}** ({item.id}): {item.description}" for item in output.test_fixtures)
        lines.append("")

    if output.mock_strategy:
        lines.extend(["## Mock Strategy", "", str(output.mock_strategy), ""])

    if output.coverage_targets:
        lines.extend(["## Coverage Targets", "", str(output.coverage_targets), ""])

    return "\n".join(lines)
