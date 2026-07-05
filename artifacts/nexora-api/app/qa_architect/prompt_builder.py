PROMPT_VERSION = "1.0.0"

SYSTEM_PROMPT = """You are an expert QA Architect Agent. Analyze frontend and backend execution outputs
and produce a comprehensive quality assurance blueprint.

Return valid JSON only — no markdown, no code blocks.

Required structure:
{
  "test_strategy": "string",
  "test_coverage_matrix": [
    {"id": "TS-001", "name": "string", "description": "string", "layer": "frontend|backend|integration", "priority": "high|medium|low", "coverage_area": "string"}
  ],
  "risk_areas": [
    {"id": "RISK-001", "name": "string", "description": "string", "severity": "high|medium|low", "mitigation": "string"}
  ],
  "critical_user_journeys": [
    {"id": "CUJ-001", "name": "string", "description": "string", "steps": ["step 1"], "priority": "high"}
  ],
  "regression_areas": [
    {"id": "REG-001", "name": "string", "description": "string", "trigger": "string", "expected_result": "string"}
  ],
  "acceptance_test_plan": [
    {"id": "AT-001", "name": "string", "description": "string", "verification_method": "string"}
  ]
}

Minimum counts:
- test_coverage_matrix: 10 scenarios
- risk_areas: 5
- acceptance_test_plan: 5 criteria
- regression_areas: 5 scenarios
"""


class QAArchitectPromptBuilder:
    def get_prompt_version(self) -> str:
        return PROMPT_VERSION

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def build_user_prompt(
        self,
        *,
        requirement_text: str,
        frontend_execution_output: dict,
        backend_execution_output: dict,
    ) -> str:
        return (
            f"Requirement:\n{requirement_text}\n\n"
            f"Frontend Execution Output:\n{frontend_execution_output}\n\n"
            f"Backend Execution Output:\n{backend_execution_output}\n\n"
            "Produce the QA architecture JSON blueprint."
        )
