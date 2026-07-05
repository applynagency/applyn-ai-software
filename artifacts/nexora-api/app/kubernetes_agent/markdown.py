from app.schemas.kubernetes_agent import KubernetesAgentOutput


def output_to_markdown(output: KubernetesAgentOutput) -> str:
    lines = ["# Kubernetes Manifest Plan", ""]

    if output.cluster_overview:
        lines.extend(["## Cluster Overview", "", output.cluster_overview, ""])

    list_sections = [
        ("Deployments", output.deployments),
        ("Services", output.services),
        ("Ingress", output.ingresses),
        ("Horizontal Pod Autoscalers", output.hpas),
        ("ConfigMaps & Secrets", output.configmaps_secrets),
        ("Network Policies", output.network_policies),
        ("Environment Overlays", output.environment_overlays),
    ]

    for title, items in list_sections:
        lines.extend([f"## {title}", ""])
        if items:
            for item in items:
                lines.append(f"- **{item.name}**: {item.description}")
        else:
            lines.append("- _None defined_")
        lines.append("")

    return "\n".join(lines)
