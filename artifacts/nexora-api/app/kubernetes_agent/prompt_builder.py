PROMPT_VERSION = "1.0.0"

SYSTEM_PROMPT = """You are an expert Kubernetes Agent. Analyze Infrastructure Architect, Docker, and
CI/CD outputs and produce a complete Kubernetes manifest plan.

Return valid JSON only — no markdown, no code blocks.

Required structure:
{
  "cluster_overview": "string",
  "deployments": [{"id": "string", "name": "string", "description": "string", "image": "string", "replicas": 0}],
  "services": [{"id": "string", "name": "string", "description": "string", "service_type": "string", "port": 0}],
  "ingresses": [{"id": "string", "name": "string", "description": "string", "host": "string", "path": "string"}],
  "hpas": [{"id": "string", "name": "string", "description": "string", "min_replicas": 0, "max_replicas": 0, "target_metric": "string"}],
  "configmaps_secrets": [{"id": "string", "name": "string", "description": "string", "kind": "string"}],
  "network_policies": [{"id": "string", "name": "string", "description": "string"}],
  "environment_overlays": [{"id": "string", "name": "string", "description": "string", "environment": "string"}]
}

Validation constraints:
- At least 3 deployments
- At least 3 services
- At least 1 ingress
- At least 1 HPA
- At least 3 configmaps/secrets
"""


class KubernetesAgentPromptBuilder:
    def get_prompt_version(self) -> str:
        return PROMPT_VERSION

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def build_user_prompt(
        self,
        *,
        requirement_text: str,
        infrastructure_architect_output: dict,
        docker_agent_output: dict,
        cicd_agent_output: dict,
    ) -> str:
        return (
            f"Requirement:\n{requirement_text}\n\n"
            f"Infrastructure Architect Output:\n{infrastructure_architect_output}\n\n"
            f"Docker Agent Output:\n{docker_agent_output}\n\n"
            f"CI/CD Agent Output:\n{cicd_agent_output}\n\n"
            "Produce the Kubernetes manifest plan JSON."
        )
