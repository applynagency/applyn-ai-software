from app.schemas.qa_architect import QAArchitectOutput


def output_to_markdown(output: QAArchitectOutput) -> str:
    lines = ["# QA Architecture Blueprint", "", "## Test Strategy", "", output.test_strategy, ""]

    sections = [
        ("Test Coverage Matrix", output.test_coverage_matrix, lambda i: f"- **{i.name}** ({i.id}): {i.description} [{i.layer}]"),
        ("Risk Areas", output.risk_areas, lambda i: f"- **{i.name}** ({i.id}): {i.description} — severity: {i.severity}"),
        ("Critical User Journeys", output.critical_user_journeys, lambda i: f"- **{i.name}** ({i.id}): {i.description}"),
        ("Regression Areas", output.regression_areas, lambda i: f"- **{i.name}** ({i.id}): {i.description}"),
        ("Acceptance Test Plan", output.acceptance_test_plan, lambda i: f"- **{i.name}** ({i.id}): {i.description}"),
    ]

    for title, items, formatter in sections:
        if items:
            lines.extend([f"## {title}", ""])
            lines.extend(formatter(item) for item in items)
            lines.append("")

    return "\n".join(lines)
