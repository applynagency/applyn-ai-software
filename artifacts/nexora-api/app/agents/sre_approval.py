import json
import re

import anthropic

from app.core.config import settings
from app.core.exceptions import AgentError
from app.core.logging import get_logger
from app.models.sre_approval import SreStatus
from app.schemas.sre_approval import SreApprovalOutput
from app.sre_approval.prompt_builder import SreApprovalPromptBuilder

logger = get_logger(__name__)


class SreApprovalAgent:
    def __init__(self):
        if not settings.ANTHROPIC_API_KEY:
            raise AgentError("ANTHROPIC_API_KEY is not configured. Add it in the Secrets panel.")
        from app.ai.compat import gateway_anthropic_client

        self.client = gateway_anthropic_client(feature="agent:sre_approval")
        self.prompt_builder = SreApprovalPromptBuilder()

    async def run(
        self,
        *,
        requirement_text: str,
        infrastructure_architect_output: dict,
        docker_agent_output: dict,
        cicd_agent_output: dict,
        kubernetes_output: dict,
        observability_output: dict,
    ) -> tuple[SreApprovalOutput, int]:
        logger.info("sre_approval_agent_start", requirement_length=len(requirement_text))

        user_prompt = self.prompt_builder.build_user_prompt(
            requirement_text=requirement_text,
            infrastructure_architect_output=infrastructure_architect_output,
            docker_agent_output=docker_agent_output,
            cicd_agent_output=cicd_agent_output,
            kubernetes_output=kubernetes_output,
            observability_output=observability_output,
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

        logger.info("sre_approval_agent_complete", tokens_used=tokens_used)
        return output, tokens_used

    def _parse_output(self, data: dict) -> SreApprovalOutput:
        status_value = data.get("sre_status") or SreStatus.SRE_REJECTED.value
        try:
            sre_status = SreStatus(status_value)
        except ValueError:
            sre_status = SreStatus.SRE_REJECTED

        def as_score(key: str) -> int:
            value = data.get(key)
            return value if isinstance(value, int) else 0

        findings = data.get("findings")
        if not isinstance(findings, list):
            findings = []

        warnings = data.get("warnings")
        if not isinstance(warnings, list):
            warnings = []

        return SreApprovalOutput(
            sre_status=sre_status,
            production_readiness_score=as_score("production_readiness_score"),
            availability_score=as_score("availability_score"),
            security_score=as_score("security_score"),
            performance_score=as_score("performance_score"),
            cost_score=as_score("cost_score"),
            operational_readiness_score=as_score("operational_readiness_score"),
            findings=[str(item) for item in findings],
            warnings=[str(item) for item in warnings],
            recommendation=str(data.get("recommendation") or ""),
        )
