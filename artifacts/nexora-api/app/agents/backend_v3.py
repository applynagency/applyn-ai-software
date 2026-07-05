import json
import re

import anthropic

from app.backend_v3.prompt_builder import BackendDeveloperV3PromptBuilder
from app.core.config import settings
from app.core.exceptions import AgentError
from app.core.logging import get_logger
from app.schemas.backend_v3 import BackendDeveloperV3Output, GeneratedFile

logger = get_logger(__name__)


class BackendDeveloperV3Agent:
    def __init__(self):
        if not settings.ANTHROPIC_API_KEY:
            raise AgentError("ANTHROPIC_API_KEY is not configured. Add it in the Secrets panel.")
        from app.ai.compat import gateway_anthropic_client

        self.client = gateway_anthropic_client(feature="agent:backend_v3")
        self.prompt_builder = BackendDeveloperV3PromptBuilder()

    async def run(
        self,
        *,
        requirement_text: str,
        backend_v2_output: dict,
    ) -> tuple[BackendDeveloperV3Output, int]:
        logger.info("backend_v3_agent_start", requirement_length=len(requirement_text))

        user_prompt = self.prompt_builder.build_user_prompt(
            requirement_text=requirement_text,
            backend_v2_output=backend_v2_output,
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

        logger.info(
            "backend_v3_agent_complete",
            tokens_used=tokens_used,
            generated_files=len(output.generated_files),
        )
        return output, tokens_used

    def _parse_generated_files(self, items: list) -> list[GeneratedFile]:
        return [
            GeneratedFile(
                path=item.get("path", ""),
                content=item.get("content", ""),
            )
            for item in items
        ]

    def _parse_output(self, data: dict) -> BackendDeveloperV3Output:
        return BackendDeveloperV3Output(
            generated_files=self._parse_generated_files(data.get("generated_files", [])),
            project_structure=data.get("project_structure") or {},
            requirements_txt=data.get("requirements_txt") or "",
            environment_variables=data.get("environment_variables") or [],
            docker_configuration=data.get("docker_configuration") or {},
            readme=data.get("readme") or "",
        )
