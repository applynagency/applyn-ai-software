import json
import re

import anthropic

from app.core.config import settings
from app.core.exceptions import AgentError
from app.core.logging import get_logger
from app.observability_agent.prompt_builder import ObservabilityAgentPromptBuilder
from app.schemas.observability_agent import (
    AlertRule,
    GrafanaDashboard,
    LoggingFlow,
    ObservabilityAgentOutput,
    SLODefinition,
)

logger = get_logger(__name__)


class ObservabilityAgent:
    def __init__(self):
        if not settings.ANTHROPIC_API_KEY:
            raise AgentError("ANTHROPIC_API_KEY is not configured. Add it in the Secrets panel.")
        from app.ai.compat import gateway_anthropic_client

        self.client = gateway_anthropic_client(feature="agent:observability_agent")
        self.prompt_builder = ObservabilityAgentPromptBuilder()

    async def run(
        self,
        *,
        requirement_text: str,
        kubernetes_output: dict,
    ) -> tuple[ObservabilityAgentOutput, int]:
        logger.info("observability_agent_start", requirement_length=len(requirement_text))

        user_prompt = self.prompt_builder.build_user_prompt(
            requirement_text=requirement_text,
            kubernetes_output=kubernetes_output,
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

        logger.info("observability_agent_complete", tokens_used=tokens_used)
        return output, tokens_used

    def _parse_output(self, data: dict) -> ObservabilityAgentOutput:
        def as_list(key: str) -> list[dict]:
            value = data.get(key)
            return value if isinstance(value, list) else []

        return ObservabilityAgentOutput(
            prometheus_configuration=str(data.get("prometheus_configuration") or ""),
            logging_architecture=str(data.get("logging_architecture") or ""),
            tracing_architecture=str(data.get("tracing_architecture") or ""),
            grafana_dashboards=[GrafanaDashboard(**item) for item in as_list("grafana_dashboards")],
            alert_rules=[AlertRule(**item) for item in as_list("alert_rules")],
            logging_flows=[LoggingFlow(**item) for item in as_list("logging_flows")],
            slo_definitions=[SLODefinition(**item) for item in as_list("slo_definitions")],
        )
