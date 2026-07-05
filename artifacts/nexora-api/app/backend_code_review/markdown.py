from app.schemas.backend_code_review import BackendCodeReviewOutput


def _format_issues(output: BackendCodeReviewOutput) -> list[str]:
    lines: list[str] = ["## Issues", ""]
    if not output.issues:
        lines.append("_No issues found._")
        lines.append("")
        return lines
    for issue in output.issues:
        lines.append(f"### {issue.title} ({issue.id})")
        lines.append(f"- **Category:** {issue.category}")
        lines.append(f"- **Severity:** {issue.severity}")
        if issue.file_path:
            lines.append(f"- **File:** `{issue.file_path}`")
        lines.append(f"- **Description:** {issue.description}")
        if issue.recommendation:
            lines.append(f"- **Recommendation:** {issue.recommendation}")
        lines.append("")
    return lines


def _format_recommendations(output: BackendCodeReviewOutput) -> list[str]:
    lines: list[str] = ["## Recommendations", ""]
    if not output.recommendations:
        lines.append("_No recommendations._")
        lines.append("")
        return lines
    for rec in output.recommendations:
        lines.append(f"- **{rec.title}** ({rec.id})")
        lines.append(f"  - Category: {rec.category}")
        lines.append(f"  - Priority: {rec.priority}")
        lines.append(f"  - {rec.description}")
    lines.append("")
    return lines


def output_to_markdown(output: BackendCodeReviewOutput) -> str:
    """Convert structured Backend Code Review output to a readable markdown document."""
    lines: list[str] = [
        "# Backend Code Review",
        "",
        f"**Review Score:** {output.review_score}",
        f"**Approval Status:** {output.approval_status.value}",
        "",
        "## Summary",
        "",
        output.summary.strip(),
        "",
    ]

    if output.category_scores:
        lines.extend(["## Category Scores", ""])
        for category, score in sorted(output.category_scores.items()):
            lines.append(f"- **{category}:** {score}")
        lines.append("")

    lines.extend(_format_issues(output))
    lines.extend(_format_recommendations(output))

    return "\n".join(lines).strip() + "\n"
