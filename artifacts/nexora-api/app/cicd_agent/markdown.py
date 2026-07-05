from app.schemas.cicd_agent import CicdAgentOutput


def output_to_markdown(output: CicdAgentOutput) -> str:
    sections = [
        ("GitHub Actions", output.github_actions),
        ("Azure DevOps", output.azure_devops),
        ("GitLab CI", output.gitlab_ci),
        ("Build Pipeline", output.build_pipeline),
        ("Release Pipeline", output.release_pipeline),
        ("Rollback Strategy", output.rollback_strategy),
    ]

    lines = ["# CI/CD Pipeline Blueprint", ""]
    for title, content in sections:
        lines.extend([f"## {title}", "", content, ""])

    return "\n".join(lines)
