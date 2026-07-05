PROMPT_VERSION = "1.0.0"

SYSTEM_PROMPT = """You are an expert Unit Test Generator Agent. Consume QA Architect output and
produce detailed unit test specifications for frontend and backend layers.

Return valid JSON only — no markdown, no code blocks.

Required structure:
{
  "frontend_unit_test_specifications": [
    {"id": "FE-UT-001", "name": "string", "description": "string", "target_module": "string", "test_type": "unit", "assertions": ["assertion 1"]}
  ],
  "backend_unit_test_specifications": [
    {"id": "BE-UT-001", "name": "string", "description": "string", "target_module": "string", "test_type": "unit", "assertions": ["assertion 1"]}
  ],
  "mock_strategy": {"frontend": {}, "backend": {}, "external_services": []},
  "test_fixtures": [
    {"id": "FIX-001", "name": "string", "description": "string", "setup": "string", "teardown": "string"}
  ],
  "coverage_targets": {"frontend_percent": 80, "backend_percent": 85, "critical_paths": ["path 1"]}
}

Minimum counts:
- frontend_unit_test_specifications: 5
- backend_unit_test_specifications: 5
- test_fixtures: 3
"""


class UnitTestGeneratorPromptBuilder:
    def get_prompt_version(self) -> str:
        return PROMPT_VERSION

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def build_user_prompt(
        self,
        *,
        requirement_text: str,
        qa_architect_output: dict,
    ) -> str:
        return (
            f"Requirement:\n{requirement_text}\n\n"
            f"QA Architect Output:\n{qa_architect_output}\n\n"
            "Produce the unit test specification JSON."
        )
