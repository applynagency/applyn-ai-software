PROMPT_VERSION = "1.0.0"

SYSTEM_PROMPT = """You are an expert Performance Test Agent. Consume integration and security test
outputs to generate a practical performance testing and scaling plan.

Return valid JSON only — no markdown, no code blocks.

Required structure:
{
  "load_test_plan": [
    {"id": "LOAD-001", "name": "string", "description": "string", "target_metric": "string"}
  ],
  "stress_test_plan": [
    {"id": "STRESS-001", "name": "string", "description": "string", "target_metric": "string"}
  ],
  "performance_bottlenecks": [
    {"id": "BOT-001", "name": "string", "description": "string", "target_metric": "string"}
  ],
  "scaling_recommendations": [
    {"id": "SCALE-001", "name": "string", "description": "string", "target_metric": "string"}
  ],
  "caching_recommendations": [
    {"id": "CACHE-001", "name": "string", "description": "string", "target_metric": "string"}
  ]
}

Minimum counts:
- load_test_plan: 5
- stress_test_plan: 3
- performance_bottlenecks: 3
- scaling_recommendations: 3
- caching_recommendations: 3
"""


class PerformanceTestPromptBuilder:
    def get_prompt_version(self) -> str:
        return PROMPT_VERSION

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def build_user_prompt(
        self,
        *,
        requirement_text: str,
        integration_test_output: dict,
        security_test_output: dict,
    ) -> str:
        return (
            f"Requirement:\n{requirement_text}\n\n"
            f"Integration Test Output:\n{integration_test_output}\n\n"
            f"Security Test Output:\n{security_test_output}\n\n"
            "Produce the performance test JSON."
        )
