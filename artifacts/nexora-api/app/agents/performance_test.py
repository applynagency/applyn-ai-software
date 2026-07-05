import json
import re
import uuid

import anthropic

from app.core.config import settings
from app.core.exceptions import AgentError
from app.core.logging import get_logger
from app.performance_test.prompt_builder import PerformanceTestPromptBuilder
from app.schemas.performance_test import PerformanceItem, PerformanceTestOutput

logger = get_logger(__name__)


class PerformanceTestAgent:
    def __init__(self):
        if not settings.ANTHROPIC_API_KEY:
            raise AgentError("ANTHROPIC_API_KEY is not configured. Add it in the Secrets panel.")
        from app.ai.compat import gateway_anthropic_client

        self.client = gateway_anthropic_client(feature="agent:performance_test")
        self.prompt_builder = PerformanceTestPromptBuilder()

    async def run(
        self,
        *,
        requirement_text: str,
        integration_test_output: dict,
        security_test_output: dict,
    ) -> tuple[PerformanceTestOutput, int]:
        logger.info("performance_test_agent_start", requirement_length=len(requirement_text))

        user_prompt = self.prompt_builder.build_user_prompt(
            requirement_text=requirement_text,
            integration_test_output=integration_test_output,
            security_test_output=security_test_output,
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

        logger.info("performance_test_agent_complete", tokens_used=tokens_used)
        return output, tokens_used

    def _parse_output(self, data: dict) -> PerformanceTestOutput:
        def uid(prefix: str) -> str:
            return f"{prefix}-{str(uuid.uuid4())[:6]}"

        def parse_items(items: list, prefix: str) -> list[PerformanceItem]:
            return [
                PerformanceItem(
                    id=item.get("id") or uid(prefix),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    target_metric=item.get("target_metric"),
                )
                for item in items
            ]

        return PerformanceTestOutput(
            load_test_plan=parse_items(data.get("load_test_plan") or [], "LOAD"),
            stress_test_plan=parse_items(data.get("stress_test_plan") or [], "STRESS"),
            performance_bottlenecks=parse_items(
                data.get("performance_bottlenecks") or [], "BOT"
            ),
            scaling_recommendations=parse_items(
                data.get("scaling_recommendations") or [], "SCALE"
            ),
            caching_recommendations=parse_items(
                data.get("caching_recommendations") or [], "CACHE"
            ),
        )
