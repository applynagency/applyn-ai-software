PROMPT_VERSION = "1.0.0"

SYSTEM_PROMPT = """You are an expert QA Approval Agent. Review Integration, Security, and
Performance test outputs to determine release readiness.

Return valid JSON only — no markdown, no code blocks.

Required structure:
{
  "qa_status": "QA_APPROVED | QA_APPROVED_WITH_WARNINGS | QA_REJECTED",
  "quality_score": 0,
  "findings": ["string"],
  "warnings": ["string"],
  "recommendation": "string"
}

Validation constraints:
- qa_status must be one of QA_APPROVED, QA_APPROVED_WITH_WARNINGS, QA_REJECTED
- quality_score must be between 0 and 100
- findings must be a non-empty list
"""


class QAApprovalPromptBuilder:
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
        performance_test_output: dict,
    ) -> str:
        return (
            f"Requirement:\n{requirement_text}\n\n"
            f"Integration Test Output:\n{integration_test_output}\n\n"
            f"Security Test Output:\n{security_test_output}\n\n"
            f"Performance Test Output:\n{performance_test_output}\n\n"
            "Produce the QA approval JSON."
        )
