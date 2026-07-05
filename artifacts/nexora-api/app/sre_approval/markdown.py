from app.schemas.sre_approval import SreApprovalOutput


def output_to_markdown(output: SreApprovalOutput) -> str:
    lines = [
        "# SRE Production Readiness Decision",
        "",
        f"- **SRE Status:** {output.sre_status.value}",
        f"- **Production Readiness Score:** {output.production_readiness_score}",
        f"- **Availability Score:** {output.availability_score}",
        f"- **Security Score:** {output.security_score}",
        f"- **Performance Score:** {output.performance_score}",
        f"- **Cost Score:** {output.cost_score}",
        f"- **Operational Readiness Score:** {output.operational_readiness_score}",
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
