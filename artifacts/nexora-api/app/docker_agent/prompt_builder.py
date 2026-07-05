PROMPT_VERSION = "1.0.0"

SYSTEM_PROMPT = """You are an expert Docker Agent. Analyze infrastructure architecture output and
produce a comprehensive containerization blueprint.

Return valid JSON only — no markdown, no code blocks.

Required structure:
{
  "dockerfile_strategy": "string",
  "docker_compose": "string",
  "container_topology": "string",
  "runtime_configuration": "string",
  "image_optimization": "string",
  "security_hardening": "string"
}

All six sections must be substantive non-empty strings covering Dockerfile design, compose layout,
service topology, runtime settings, image optimization, and container security hardening.
"""


class DockerAgentPromptBuilder:
    def get_prompt_version(self) -> str:
        return PROMPT_VERSION

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def build_user_prompt(
        self,
        *,
        requirement_text: str,
        infrastructure_architect_output: dict,
    ) -> str:
        return (
            f"Requirement:\n{requirement_text}\n\n"
            f"Infrastructure Architect Output:\n{infrastructure_architect_output}\n\n"
            "Produce the Docker containerization JSON blueprint."
        )
