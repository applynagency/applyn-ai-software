import json
import re
import uuid

import anthropic

from app.core.config import settings
from app.core.exceptions import AgentError
from app.core.logging import get_logger
from app.schemas.security_test import SecurityAssessmentItem, SecurityTestOutput
from app.security_test.prompt_builder import SecurityTestPromptBuilder

logger = get_logger(__name__)


class SecurityTestAgent:
    def __init__(self):
        if not settings.ANTHROPIC_API_KEY:
            raise AgentError("ANTHROPIC_API_KEY is not configured. Add it in the Secrets panel.")
        from app.ai.compat import gateway_anthropic_client

        self.client = gateway_anthropic_client(feature="agent:security_test")
        self.prompt_builder = SecurityTestPromptBuilder()

    async def run(
        self,
        *,
        requirement_text: str,
        frontend_execution_output: dict,
        backend_execution_output: dict,
        integration_test_output: dict,
    ) -> tuple[SecurityTestOutput, int]:
        logger.info("security_test_agent_start", requirement_length=len(requirement_text))

        user_prompt = self.prompt_builder.build_user_prompt(
            requirement_text=requirement_text,
            frontend_execution_output=frontend_execution_output,
            backend_execution_output=backend_execution_output,
            integration_test_output=integration_test_output,
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

        logger.info("security_test_agent_complete", tokens_used=tokens_used)
        return output, tokens_used

    def _parse_output(self, data: dict) -> SecurityTestOutput:
        def uid(prefix: str) -> str:
            return f"{prefix}-{str(uuid.uuid4())[:6]}"

        def parse_items(items: list, prefix: str) -> list[SecurityAssessmentItem]:
            return [
                SecurityAssessmentItem(
                    id=item.get("id") or uid(prefix),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    severity=item.get("severity"),
                    recommendation=item.get("recommendation"),
                )
                for item in items
            ]

        return SecurityTestOutput(
            owasp_assessment=parse_items(data.get("owasp_assessment") or [], "OWASP"),
            authentication_review=parse_items(data.get("authentication_review") or [], "AUTHN"),
            authorization_review=parse_items(data.get("authorization_review") or [], "AUTHZ"),
            input_validation_review=parse_items(data.get("input_validation_review") or [], "INPUT"),
            dependency_security_scan=parse_items(data.get("dependency_security_scan") or [], "DEP"),
            secrets_exposure_review=parse_items(data.get("secrets_exposure_review") or [], "SEC"),
        )
