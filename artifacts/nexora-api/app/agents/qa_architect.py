import json
import re
import uuid

import anthropic

from app.core.config import settings
from app.core.exceptions import AgentError
from app.core.logging import get_logger
from app.qa_architect.prompt_builder import QAArchitectPromptBuilder
from app.schemas.qa_architect import (
    AcceptanceCriterion,
    QAArchitectOutput,
    RegressionScenario,
    RiskArea,
    TestScenario,
    UserJourney,
)

logger = get_logger(__name__)


class QAArchitectAgent:
    def __init__(self):
        if not settings.ANTHROPIC_API_KEY:
            raise AgentError("ANTHROPIC_API_KEY is not configured. Add it in the Secrets panel.")
        from app.ai.compat import gateway_anthropic_client

        self.client = gateway_anthropic_client(feature="agent:qa_architect")
        self.prompt_builder = QAArchitectPromptBuilder()

    async def run(
        self,
        *,
        requirement_text: str,
        frontend_execution_output: dict,
        backend_execution_output: dict,
    ) -> tuple[QAArchitectOutput, int]:
        logger.info("qa_architect_agent_start", requirement_length=len(requirement_text))

        user_prompt = self.prompt_builder.build_user_prompt(
            requirement_text=requirement_text,
            frontend_execution_output=frontend_execution_output,
            backend_execution_output=backend_execution_output,
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

        logger.info("qa_architect_agent_complete", tokens_used=tokens_used)
        return output, tokens_used

    def _parse_output(self, data: dict) -> QAArchitectOutput:
        def uid(prefix: str) -> str:
            return f"{prefix}-{str(uuid.uuid4())[:6]}"

        return QAArchitectOutput(
            test_strategy=data.get("test_strategy") or "",
            test_coverage_matrix=[
                TestScenario(
                    id=item.get("id") or uid("TS"),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    layer=item.get("layer", "integration"),
                    priority=item.get("priority", "medium"),
                    coverage_area=item.get("coverage_area"),
                )
                for item in data.get("test_coverage_matrix") or []
            ],
            risk_areas=[
                RiskArea(
                    id=item.get("id") or uid("RISK"),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    severity=item.get("severity", "medium"),
                    mitigation=item.get("mitigation"),
                )
                for item in data.get("risk_areas") or []
            ],
            critical_user_journeys=[
                UserJourney(
                    id=item.get("id") or uid("CUJ"),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    steps=item.get("steps") or [],
                    priority=item.get("priority", "high"),
                )
                for item in data.get("critical_user_journeys") or []
            ],
            regression_areas=[
                RegressionScenario(
                    id=item.get("id") or uid("REG"),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    trigger=item.get("trigger"),
                    expected_result=item.get("expected_result"),
                )
                for item in data.get("regression_areas") or []
            ],
            acceptance_test_plan=[
                AcceptanceCriterion(
                    id=item.get("id") or uid("AT"),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    verification_method=item.get("verification_method"),
                )
                for item in data.get("acceptance_test_plan") or []
            ],
        )
