PROMPT_VERSION = "1.0.0"

SYSTEM_PROMPT = """You are an expert Integration Test Agent. Consume frontend execution output,
backend execution output, and unit test output to generate a complete integration test plan.

Return valid JSON only — no markdown, no code blocks.

Required structure:
{
  "api_test_cases": [
    {"id": "API-001", "name": "string", "description": "string", "expected_result": "string"}
  ],
  "frontend_backend_flows": [
    {"id": "FLOW-001", "name": "string", "description": "string", "expected_result": "string"}
  ],
  "database_validation": [
    {"id": "DB-001", "name": "string", "description": "string", "expected_result": "string"}
  ],
  "integration_coverage": {"covered_endpoints": [], "covered_journeys": [], "notes": "string"}
}

Minimum counts:
- api_test_cases: 8
- frontend_backend_flows: 5
- database_validation: 5
- integration_coverage: non-empty object
"""


class IntegrationTestPromptBuilder:
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
        unit_test_output: dict,
    ) -> str:
        return (
            f"Requirement:\n{requirement_text}\n\n"
            f"Frontend Execution Output:\n{frontend_execution_output}\n\n"
            f"Backend Execution Output:\n{backend_execution_output}\n\n"
            f"Unit Test Output:\n{unit_test_output}\n\n"
            "Produce the integration test JSON."
        )
