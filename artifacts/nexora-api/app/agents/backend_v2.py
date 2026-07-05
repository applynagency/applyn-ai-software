import json
import re
import uuid

import anthropic

from app.backend_v2.prompt_builder import BackendDeveloperV2PromptBuilder
from app.core.config import settings
from app.core.exceptions import AgentError
from app.core.logging import get_logger
from app.schemas.backend_v2 import BackendDeveloperV2Output, FileSpecItem

logger = get_logger(__name__)


class BackendDeveloperV2Agent:
    def __init__(self):
        if not settings.ANTHROPIC_API_KEY:
            raise AgentError("ANTHROPIC_API_KEY is not configured. Add it in the Secrets panel.")
        from app.ai.compat import gateway_anthropic_client

        self.client = gateway_anthropic_client(feature="agent:backend_v2")
        self.prompt_builder = BackendDeveloperV2PromptBuilder()

    async def run(
        self,
        *,
        requirement_text: str,
        backend_v1_output: dict,
    ) -> tuple[BackendDeveloperV2Output, int]:
        logger.info("backend_v2_agent_start", requirement_length=len(requirement_text))

        user_prompt = self.prompt_builder.build_user_prompt(
            requirement_text=requirement_text,
            backend_v1_output=backend_v1_output,
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
            "backend_v2_agent_complete",
            tokens_used=tokens_used,
            router_files=len(output.router_files),
        )
        return output, tokens_used

    def _parse_file_list(self, items: list, prefix: str) -> list[FileSpecItem]:
        def uid(p: str) -> str:
            return f"{p}-{str(uuid.uuid4())[:6]}"

        return [
            FileSpecItem(
                id=item.get("id", uid(prefix)),
                path=item.get("path", ""),
                name=item.get("name", ""),
                description=item.get("description", ""),
                purpose=item.get("purpose"),
                exports=item.get("exports", []),
                dependencies=item.get("dependencies", []),
            )
            for item in items
        ]

    def _parse_output(self, data: dict) -> BackendDeveloperV2Output:
        return BackendDeveloperV2Output(
            file_structure=data.get("file_structure") or {},
            router_files=self._parse_file_list(data.get("router_files", []), "RT"),
            schema_files=self._parse_file_list(data.get("schema_files", []), "SC"),
            model_files=self._parse_file_list(data.get("model_files", []), "MD"),
            repository_files=self._parse_file_list(data.get("repository_files", []), "RP"),
            service_files=self._parse_file_list(data.get("service_files", []), "SV"),
            dependency_files=self._parse_file_list(data.get("dependency_files", []), "DP"),
            middleware_files=self._parse_file_list(data.get("middleware_files", []), "MW"),
            background_job_files=self._parse_file_list(data.get("background_job_files", []), "BJ"),
            integration_files=self._parse_file_list(data.get("integration_files", []), "IN"),
            configuration_files=self._parse_file_list(data.get("configuration_files", []), "CF"),
            migration_files=self._parse_file_list(data.get("migration_files", []), "MG"),
            test_files=self._parse_file_list(data.get("test_files", []), "TS"),
            infrastructure_files=self._parse_file_list(data.get("infrastructure_files", []), "IF"),
        )
