import json
import re

import anthropic

from app.cicd_agent.prompt_builder import CicdAgentPromptBuilder
from app.core.config import settings
from app.core.exceptions import AgentError
from app.core.logging import get_logger
from app.schemas.cicd_agent import CicdAgentOutput

logger = get_logger(__name__)


class CicdAgent:
    def __init__(self):
        if not settings.ANTHROPIC_API_KEY:
            raise AgentError("ANTHROPIC_API_KEY is not configured. Add it in the Secrets panel.")
        from app.ai.compat import gateway_anthropic_client

        self.client = gateway_anthropic_client(feature="agent:cicd_agent")
        self.prompt_builder = CicdAgentPromptBuilder()

    async def run(
        self,
        *,
        requirement_text: str,
        docker_agent_output: dict,
    ) -> tuple[CicdAgentOutput, int]:
        logger.info("cicd_agent_start", requirement_length=len(requirement_text))

        user_prompt = self.prompt_builder.build_user_prompt(
            requirement_text=requirement_text,
            docker_agent_output=docker_agent_output,
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

        logger.info("cicd_agent_complete", tokens_used=tokens_used)
        return output, tokens_used

    def _parse_output(self, data: dict) -> CicdAgentOutput:
        return CicdAgentOutput(
            github_actions=data.get("github_actions") or "",
            azure_devops=data.get("azure_devops") or "",
            gitlab_ci=data.get("gitlab_ci") or "",
            build_pipeline=data.get("build_pipeline") or "",
            release_pipeline=data.get("release_pipeline") or "",
            rollback_strategy=data.get("rollback_strategy") or "",
        )
