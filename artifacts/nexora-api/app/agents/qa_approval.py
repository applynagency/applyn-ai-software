import json
import re

import anthropic

from app.core.config import settings
from app.core.exceptions import AgentError
from app.core.logging import get_logger
from app.models.qa_approval import QAStatus
from app.qa_approval.prompt_builder import QAApprovalPromptBuilder
from app.schemas.qa_approval import QAApprovalOutput

logger = get_logger(__name__)


class QAApprovalAgent:
    def __init__(self):
        if not settings.ANTHROPIC_API_KEY:
            raise AgentError("ANTHROPIC_API_KEY is not configured. Add it in the Secrets panel.")
        from app.ai.compat import gateway_anthropic_client

        self.client = gateway_anthropic_client(feature="agent:qa_approval")
        self.prompt_builder = QAApprovalPromptBuilder()

    async def run(
        self,
        *,
        requirement_text: str,
        integration_test_output: dict,
        security_test_output: dict,
        performance_test_output: dict,
    ) -> tuple[QAApprovalOutput, int]:
        logger.info("qa_approval_agent_start", requirement_length=len(requirement_text))

        user_prompt = self.prompt_builder.build_user_prompt(
            requirement_text=requirement_text,
            integration_test_output=integration_test_output,
            security_test_output=security_test_output,
            performance_test_output=performance_test_output,
        )

        try:
            message = await self.client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=settings.ANTHROPIC_MAX_TOKENS,
                system=self.prompt_builder.get_system_prompt(),
                messages=[{"role": "user", "content": user_prompt}],
            )
        except anthropic.AuthenticationError as exc:
            raise AgentError("Invalid ANTHROPIC_API_KEY — check your Secrets panel.") from exc
        except anthropic.RateLimitError as exc:
            raise AgentError("Anthropic rate limit hit — please retry in a moment.") from exc
        except Exception as exc:
            raise AgentError(f"LLM call failed: {str(exc)}") from exc

        tokens_used = (message.usage.input_tokens + message.usage.output_tokens) if message.usage else 0
        raw_content = ""
        for block in message.content:
            if block.type == "text":
                raw_content = block.text
                break

        if not raw_content:
            raise AgentError("Empty response from Claude")

        raw_content = re.sub(r"^```(?:json)?\s*", "", raw_content.strip())
        raw_content = re.sub(r"\s*```$", "", raw_content.strip())

        try:
            data = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            raise AgentError(f"Failed to parse Claude's response as JSON: {str(exc)}") from exc

        try:
            output = self._parse_output(data)
        except Exception as exc:
            raise AgentError(f"Failed to structure agent output: {str(exc)}") from exc

        logger.info("qa_approval_agent_complete", tokens_used=tokens_used)
        return output, tokens_used

    def _parse_output(self, data: dict) -> QAApprovalOutput:
        status_value = data.get("qa_status") or QAStatus.QA_REJECTED.value
        try:
            qa_status = QAStatus(status_value)
        except ValueError:
            qa_status = QAStatus.QA_REJECTED

        quality_score = data.get("quality_score")
        if not isinstance(quality_score, int):
            quality_score = 0

        findings = data.get("findings")
        if not isinstance(findings, list):
            findings = []

        warnings = data.get("warnings")
        if not isinstance(warnings, list):
            warnings = []

        return QAApprovalOutput(
            qa_status=qa_status,
            quality_score=quality_score,
            findings=[str(item) for item in findings],
            warnings=[str(item) for item in warnings],
            recommendation=str(data.get("recommendation") or ""),
        )
