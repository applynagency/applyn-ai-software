import json
import re
import uuid

import anthropic

from app.core.config import settings
from app.core.exceptions import AgentError
from app.core.logging import get_logger
from app.frontend_v1.prompt_builder import FrontendDeveloperV1PromptBuilder
from app.schemas.frontend_v1 import (
    ComponentStructureItem,
    FormArchitectureItem,
    FrontendDeveloperV1Output,
    LayoutStructureItem,
    ModuleBreakdownItem,
    PageStructureItem,
    RouteStructureItem,
)

logger = get_logger(__name__)


class FrontendDeveloperV1Agent:
    def __init__(self):
        if not settings.ANTHROPIC_API_KEY:
            raise AgentError("ANTHROPIC_API_KEY is not configured. Add it in the Secrets panel.")
        from app.ai.compat import gateway_anthropic_client

        self.client = gateway_anthropic_client(feature="agent:frontend_v1")
        self.prompt_builder = FrontendDeveloperV1PromptBuilder()

    async def run(
        self,
        *,
        requirement_text: str,
        frontend_architect_output: dict,
    ) -> tuple[FrontendDeveloperV1Output, int]:
        logger.info("frontend_v1_agent_start", requirement_length=len(requirement_text))

        user_prompt = self.prompt_builder.build_user_prompt(
            requirement_text=requirement_text,
            frontend_architect_output=frontend_architect_output,
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
            "frontend_v1_agent_complete",
            tokens_used=tokens_used,
            pages=len(output.page_structure),
        )
        return output, tokens_used

    def _parse_output(self, data: dict) -> FrontendDeveloperV1Output:
        def uid(prefix: str) -> str:
            return f"{prefix}-{str(uuid.uuid4())[:6]}"

        return FrontendDeveloperV1Output(
            project_structure=data.get("project_structure") or {},
            route_structure=[
                RouteStructureItem(
                    id=item.get("id", uid("RT")),
                    path=item.get("path", "/"),
                    name=item.get("name", ""),
                    page_id=item.get("page_id"),
                    layout_id=item.get("layout_id"),
                )
                for item in data.get("route_structure", [])
            ],
            layout_structure=[
                LayoutStructureItem(
                    id=item.get("id", uid("LY")),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    file_path=item.get("file_path"),
                )
                for item in data.get("layout_structure", [])
            ],
            page_structure=[
                PageStructureItem(
                    id=item.get("id", uid("PG")),
                    name=item.get("name", ""),
                    route=item.get("route", "/"),
                    file_path=item.get("file_path", ""),
                    purpose=item.get("purpose", ""),
                )
                for item in data.get("page_structure", [])
            ],
            component_structure=[
                ComponentStructureItem(
                    id=item.get("id", uid("CMP")),
                    name=item.get("name", ""),
                    category=item.get("category", "general"),
                    file_path=item.get("file_path", ""),
                    description=item.get("description", ""),
                )
                for item in data.get("component_structure", [])
            ],
            api_client_structure=data.get("api_client_structure") or {},
            state_management=data.get("state_management") or {},
            form_architecture=[
                FormArchitectureItem(
                    id=item.get("id", uid("FRM")),
                    name=item.get("name", ""),
                    page_id=item.get("page_id", ""),
                    fields=item.get("fields", []),
                    validation_approach=item.get("validation_approach"),
                )
                for item in data.get("form_architecture", [])
            ],
            validation_strategy=data.get("validation_strategy") or {},
            folder_organization=data.get("folder_organization") or {},
            development_conventions=data.get("development_conventions", []),
            module_breakdown=[
                ModuleBreakdownItem(
                    id=item.get("id", uid("MOD")),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    pages=item.get("pages", []),
                    components=item.get("components", []),
                )
                for item in data.get("module_breakdown", [])
            ],
        )
