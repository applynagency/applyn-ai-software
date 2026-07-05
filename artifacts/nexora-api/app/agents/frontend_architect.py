import json
import re
import uuid

import anthropic

from app.core.config import settings
from app.core.exceptions import AgentError
from app.core.logging import get_logger
from app.frontend_architect.prompt_builder import FrontendArchitectPromptBuilder
from app.schemas.frontend_architect import (
    ComponentDefinition,
    FormDefinition,
    FrontendArchitectOutput,
    LayoutDefinition,
    PageDefinition,
    RouteDefinition,
)

logger = get_logger(__name__)


class FrontendArchitectAgent:
    def __init__(self):
        if not settings.ANTHROPIC_API_KEY:
            raise AgentError("ANTHROPIC_API_KEY is not configured. Add it in the Secrets panel.")
        from app.ai.compat import gateway_anthropic_client

        self.client = gateway_anthropic_client(feature="agent:frontend_architect")
        self.prompt_builder = FrontendArchitectPromptBuilder()

    async def run(
        self,
        *,
        requirement_text: str,
        uiux_output: dict,
    ) -> tuple[FrontendArchitectOutput, int]:
        logger.info("frontend_architect_agent_start", requirement_length=len(requirement_text))

        user_prompt = self.prompt_builder.build_user_prompt(
            requirement_text=requirement_text,
            uiux_output=uiux_output,
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
            "frontend_architect_agent_complete",
            tokens_used=tokens_used,
            pages=len(output.page_architecture),
        )
        return output, tokens_used

    def _parse_output(self, data: dict) -> FrontendArchitectOutput:
        def uid(prefix: str) -> str:
            return f"{prefix}-{str(uuid.uuid4())[:6]}"

        return FrontendArchitectOutput(
            frontend_stack=data.get("frontend_stack") or {},
            routing_architecture=[
                RouteDefinition(
                    id=item.get("id", uid("RT")),
                    path=item.get("path", "/"),
                    name=item.get("name", ""),
                    page_id=item.get("page_id"),
                    layout=item.get("layout"),
                    auth_required=item.get("auth_required", True),
                )
                for item in data.get("routing_architecture", [])
            ],
            page_architecture=[
                PageDefinition(
                    id=item.get("id", uid("PG")),
                    name=item.get("name", ""),
                    route=item.get("route", "/"),
                    purpose=item.get("purpose", ""),
                    layout_id=item.get("layout_id"),
                )
                for item in data.get("page_architecture", [])
            ],
            layout_architecture=[
                LayoutDefinition(
                    id=item.get("id", uid("LY")),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    regions=item.get("regions", []),
                )
                for item in data.get("layout_architecture", [])
            ],
            component_architecture=[
                ComponentDefinition(
                    id=item.get("id", uid("CMP")),
                    name=item.get("name", ""),
                    category=item.get("category", "general"),
                    description=item.get("description", ""),
                    props=item.get("props", []),
                )
                for item in data.get("component_architecture", [])
            ],
            state_management=data.get("state_management") or {},
            api_integration=data.get("api_integration") or {},
            authentication=data.get("authentication") or {},
            forms=[
                FormDefinition(
                    id=item.get("id", uid("FRM")),
                    name=item.get("name", ""),
                    page_id=item.get("page_id", ""),
                    fields=item.get("fields", []),
                    validation_strategy=item.get("validation_strategy"),
                )
                for item in data.get("forms", [])
            ],
            design_system_mapping=data.get("design_system_mapping") or {},
            folder_structure=data.get("folder_structure") or {},
            deployment_architecture=data.get("deployment_architecture") or {},
            development_guidelines=data.get("development_guidelines", []),
        )
