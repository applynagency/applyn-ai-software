from app.schemas.docker_agent import DockerAgentOutput


def output_to_markdown(output: DockerAgentOutput) -> str:
    sections = [
        ("Dockerfile Strategy", output.dockerfile_strategy),
        ("Docker Compose", output.docker_compose),
        ("Container Topology", output.container_topology),
        ("Runtime Configuration", output.runtime_configuration),
        ("Image Optimization", output.image_optimization),
        ("Security Hardening", output.security_hardening),
    ]

    lines = ["# Docker Containerization Blueprint", ""]
    for title, content in sections:
        lines.extend([f"## {title}", "", content, ""])

    return "\n".join(lines)
