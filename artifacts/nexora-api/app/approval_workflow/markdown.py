from app.schemas.approval import ApprovalWorkflowOutput


def output_to_markdown(output: ApprovalWorkflowOutput) -> str:
    """Convert structured Approval Workflow output to a readable markdown document."""
    lines: list[str] = [
        "# Approval Workflow Package",
        "",
        "## Summary",
        "",
        f"- **Approval Status:** {output.approval_status}",
        f"- **Recommendation:** {output.recommendation}",
        "",
    ]

    summary = output.approval_summary or {}
    review_summary = summary.get("review_summary") or {}
    if review_summary:
        lines.extend(["## Review Summary", ""])
        lines.append(
            f"- **Frontend Execution:** {review_summary.get('frontend_execution_status', '—')}"
        )
        lines.append(
            f"- **Frontend Review:** {review_summary.get('frontend_review_status', '—')}"
        )
        lines.append(f"- **Assembly:** {review_summary.get('assembly_status', '—')}")
        if review_summary.get("review_score") is not None:
            lines.append(f"- **Review Score:** {review_summary['review_score']}")
        lines.append("")

    package = summary.get("approval_package") or {}
    if package:
        lines.extend(["## Approval Package", ""])
        lines.append(f"- **Name:** {package.get('name', 'unknown')}")
        lines.append(f"- **Version:** {package.get('version', 'unknown')}")
        lines.append(f"- **Backend Included:** {package.get('backend_included', False)}")
        lines.append(
            f"- **Environment Variables:** {package.get('environment_variable_count', 0)}"
        )
        lines.append("")

    if output.review_checklist:
        lines.extend(["## Approval Checklist", ""])
        for item in output.review_checklist:
            status = item.get("status", "unknown")
            lines.append(
                f"- [{status.upper()}] {item.get('category', '')}: {item.get('item', '')}"
            )
        lines.append("")

    readiness = output.deployment_readiness or {}
    if readiness:
        lines.extend(["## Deployment Readiness Report", ""])
        lines.append(f"- **Ready for Deployment:** {readiness.get('ready_for_deployment', False)}")
        lines.append(f"- **Readiness Score:** {readiness.get('readiness_score', 0)}")
        blocking = readiness.get("blocking_issues") or []
        if blocking:
            lines.append("- **Blocking Issues:**")
            for issue in blocking:
                lines.append(f"  - {issue}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"
