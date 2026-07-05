import json
import re
import uuid

import anthropic

from app.core.config import settings
from app.core.exceptions import AgentError
from app.core.logging import get_logger
from app.infrastructure_architect.prompt_builder import InfrastructureArchitectPromptBuilder
from app.schemas.infrastructure_architect import (
    BackupRecoveryPlan,
    Environment,
    InfrastructureArchitectOutput,
    ScalingRule,
    SecurityControl,
)

logger = get_logger(__name__)


class InfrastructureArchitectAgent:
    def __init__(self):
        if not settings.ANTHROPIC_API_KEY:
            raise AgentError("ANTHROPIC_API_KEY is not configured. Add it in the Secrets panel.")
        from app.ai.compat import gateway_anthropic_client

        self.client = gateway_anthropic_client(feature="agent:infrastructure_architect")
        self.prompt_builder = InfrastructureArchitectPromptBuilder()

    async def run(
        self,
        *,
        requirement_text: str,
        frontend_execution_output: dict,
        backend_execution_output: dict,
        qa_approval_output: dict,
    ) -> tuple[InfrastructureArchitectOutput, int]:
        logger.info("infrastructure_architect_agent_start", requirement_length=len(requirement_text))

        user_prompt = self.prompt_builder.build_user_prompt(
            requirement_text=requirement_text,
            frontend_execution_output=frontend_execution_output,
            backend_execution_output=backend_execution_output,
            qa_approval_output=qa_approval_output,
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

        logger.info("infrastructure_architect_agent_complete", tokens_used=tokens_used)
        return output, tokens_used

    def _parse_output(self, data: dict) -> InfrastructureArchitectOutput:
        def uid(prefix: str) -> str:
            return f"{prefix}-{str(uuid.uuid4())[:6]}"

        return InfrastructureArchitectOutput(
            cloud_architecture=data.get("cloud_architecture") or "",
            network_topology=data.get("network_topology") or "",
            environment_design=data.get("environment_design") or "",
            environments=[
                Environment(
                    id=item.get("id") or uid("ENV"),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    purpose=item.get("purpose"),
                    region=item.get("region"),
                )
                for item in data.get("environments") or []
            ],
            scaling_strategy=data.get("scaling_strategy") or "",
            scaling_rules=[
                ScalingRule(
                    id=item.get("id") or uid("SCALE"),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    metric=item.get("metric"),
                    threshold=item.get("threshold"),
                )
                for item in data.get("scaling_rules") or []
            ],
            ha_strategy=data.get("ha_strategy") or "",
            disaster_recovery=data.get("disaster_recovery") or "",
            security_controls=[
                SecurityControl(
                    id=item.get("id") or uid("SEC"),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    control_type=item.get("control_type"),
                    implementation=item.get("implementation"),
                )
                for item in data.get("security_controls") or []
            ],
            backup_recovery_plans=[
                BackupRecoveryPlan(
                    id=item.get("id") or uid("BR"),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    rpo=item.get("rpo"),
                    rto=item.get("rto"),
                )
                for item in data.get("backup_recovery_plans") or []
            ],
        )
