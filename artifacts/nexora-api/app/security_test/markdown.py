from app.schemas.security_test import SecurityTestOutput


def output_to_markdown(output: SecurityTestOutput) -> str:
    lines = ["# Security Test Assessment", ""]

    if output.owasp_assessment:
        lines.extend(["## OWASP Assessment", ""])
        lines.extend(f"- **{item.name}** ({item.id}): {item.description}" for item in output.owasp_assessment)
        lines.append("")

    if output.authentication_review:
        lines.extend(["## Authentication Review", ""])
        lines.extend(
            f"- **{item.name}** ({item.id}): {item.description}"
            for item in output.authentication_review
        )
        lines.append("")

    if output.authorization_review:
        lines.extend(["## Authorization Review", ""])
        lines.extend(
            f"- **{item.name}** ({item.id}): {item.description}"
            for item in output.authorization_review
        )
        lines.append("")

    if output.input_validation_review:
        lines.extend(["## Input Validation Review", ""])
        lines.extend(
            f"- **{item.name}** ({item.id}): {item.description}"
            for item in output.input_validation_review
        )
        lines.append("")

    if output.dependency_security_scan:
        lines.extend(["## Dependency Security Scan", ""])
        lines.extend(
            f"- **{item.name}** ({item.id}): {item.description}"
            for item in output.dependency_security_scan
        )
        lines.append("")

    if output.secrets_exposure_review:
        lines.extend(["## Secrets Exposure Review", ""])
        lines.extend(
            f"- **{item.name}** ({item.id}): {item.description}"
            for item in output.secrets_exposure_review
        )
        lines.append("")

    return "\n".join(lines)
