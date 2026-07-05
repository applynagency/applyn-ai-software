PROMPT_VERSION = "1.0.0"

SYSTEM_PROMPT = """You are an expert CI/CD Agent. Analyze Docker containerization output and produce
a comprehensive continuous integration and delivery blueprint.

Return valid JSON only — no markdown, no code blocks.

Required structure:
{
  "github_actions": "string",
  "azure_devops": "string",
  "gitlab_ci": "string",
  "build_pipeline": "string",
  "release_pipeline": "string",
  "rollback_strategy": "string"
}

All six sections must be substantive non-empty strings covering GitHub Actions, Azure DevOps,
GitLab CI configurations, build pipeline, release pipeline, and rollback strategy.
"""


class CicdAgentPromptBuilder:
    def get_prompt_version(self) -> str:
        return PROMPT_VERSION

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def build_user_prompt(
        self,
        *,
        requirement_text: str,
        docker_agent_output: dict,
    ) -> str:
        return (
            f"Requirement:\n{requirement_text}\n\n"
            f"Docker Agent Output:\n{docker_agent_output}\n\n"
            "Produce the CI/CD pipeline JSON blueprint."
        )
