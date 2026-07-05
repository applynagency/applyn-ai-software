from app.schemas.backend_execution import BackendExecutionOutput


def _format_step_result(title: str, results: dict) -> list[str]:
    lines = [f"## {title}", ""]
    if not results:
        lines.append("_Not executed._")
        lines.append("")
        return lines
    lines.append(f"- **Status:** {results.get('status', 'unknown')}")
    lines.append(f"- **Exit Code:** {results.get('exit_code', '—')}")
    if results.get("duration_ms") is not None:
        lines.append(f"- **Duration:** {results['duration_ms']}ms")
    if results.get("command"):
        lines.append(f"- **Command:** `{results['command']}`")
    if results.get("stderr"):
        lines.append("")
        lines.append("```")
        lines.append(str(results["stderr"])[:2000])
        lines.append("```")
    lines.append("")
    return lines


def output_to_markdown(output: BackendExecutionOutput) -> str:
    """Convert structured Backend Execution output to a readable markdown document."""
    lines: list[str] = [
        "# Backend Execution Report",
        "",
        "## Summary",
        "",
        f"- **Build Status:** {output.build_status}",
        f"- **Validation Status:** {output.validation_status}",
        f"- **Approval Status:** {output.approval_status}",
        "",
    ]

    for title, results in [
        ("Ruff Results", output.ruff_results),
        ("MyPy Results", output.mypy_results),
        ("Pytest Results", output.pytest_results),
        ("Migration Results", output.migration_results),
        ("Startup Validation", output.startup_results),
        ("Dependency Verification", output.dependency_results),
        ("Environment Validation", output.environment_results),
    ]:
        lines.extend(_format_step_result(title, results))

    lines.extend(["## Execution Logs", ""])
    for log_entry in output.execution_logs:
        lines.append(f"- {log_entry}")
    lines.append("")

    return "\n".join(lines).strip() + "\n"
