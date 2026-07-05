from app.schemas.qa_approval import QAApprovalOutput


def output_to_markdown(output: QAApprovalOutput) -> str:
    lines = [
        "# QA Approval Decision",
        "",
        f"- **QA Status:** {output.qa_status.value}",
        f"- **Quality Score:** {output.quality_score}",
        "",
    ]

    if output.findings:
        lines.extend(["## Findings", ""])
        lines.extend(f"- {item}" for item in output.findings)
        lines.append("")

    if output.warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {item}" for item in output.warnings)
        lines.append("")

    if output.recommendation:
        lines.extend(["## Recommendation", "", output.recommendation, ""])

    return "\n".join(lines)
