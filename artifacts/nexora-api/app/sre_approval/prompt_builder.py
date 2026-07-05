PROMPT_VERSION = "1.0.0"

SYSTEM_PROMPT = """You are an expert Staff SRE Approval Agent. Review the Infrastructure, Docker,
CI/CD, Kubernetes, and Observability outputs to determine production readiness.

Return valid JSON only — no markdown, no code blocks.

Required structure:
{
  "sre_status": "SRE_APPROVED | SRE_APPROVED_WITH_WARNINGS | SRE_REJECTED",
  "production_readiness_score": 0,
  "availability_score": 0,
  "security_score": 0,
  "performance_score": 0,
  "cost_score": 0,
  "operational_readiness_score": 0,
  "findings": ["string"],
  "warnings": ["string"],
  "recommendation": "string"
}

Validation constraints:
- sre_status must be one of SRE_APPROVED, SRE_APPROVED_WITH_WARNINGS, SRE_REJECTED
- all scores must be between 0 and 100
- findings must be a non-empty list
- recommendation must be non-empty
"""


class SreApprovalPromptBuilder:
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
        kubernetes_output: dict,
        observability_output: dict,
    ) -> str:
        return (
            f"Requirement:\n{requirement_text}\n\n"
            f"Infrastructure Architect Output:\n{infrastructure_architect_output}\n\n"
            f"Docker Agent Output:\n{docker_agent_output}\n\n"
            f"CI/CD Agent Output:\n{cicd_agent_output}\n\n"
            f"Kubernetes Output:\n{kubernetes_output}\n\n"
            f"Observability Output:\n{observability_output}\n\n"
            "Produce the SRE production readiness approval JSON."
        )
