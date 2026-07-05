import json
import re
import uuid

import anthropic

from app.core.config import settings
from app.core.exceptions import AgentError
from app.core.logging import get_logger
from app.schemas.uiux_designer import (
    ComponentItem,
    NavigationGroup,
    PageHierarchyItem,
    RoleScreenMapping,
    ScreenItem,
    UIUXDesignerOutput,
    UIUXUserFlow,
)
from app.uiux_designer.prompt_builder import UIUXPromptBuilder

logger = get_logger(__name__)


class UIUXDesignerAgent:
    def __init__(self):
        if not settings.ANTHROPIC_API_KEY:
            raise AgentError("ANTHROPIC_API_KEY is not configured. Add it in the Secrets panel.")
        from app.ai.compat import gateway_anthropic_client

        self.client = gateway_anthropic_client(feature="agent:uiux_designer")
        self.prompt_builder = UIUXPromptBuilder()

    async def run(
        self,
        *,
        requirement_text: str,
        business_analyst_output: dict,
    ) -> tuple[UIUXDesignerOutput, int]:
        logger.info("uiux_designer_agent_start", requirement_length=len(requirement_text))

        user_prompt = self.prompt_builder.build_user_prompt(
            requirement_text=requirement_text,
            business_analyst_output=business_analyst_output,
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
            "uiux_designer_agent_complete",
            tokens_used=tokens_used,
            screens=len(output.screen_inventory),
        )
        return output, tokens_used

    def _parse_output(self, data: dict) -> UIUXDesignerOutput:
        def uid(prefix: str) -> str:
            return f"{prefix}-{str(uuid.uuid4())[:6]}"

        return UIUXDesignerOutput(
            information_architecture=data.get("information_architecture") or {},
            navigation_structure=[
                NavigationGroup(
                    id=item.get("id", uid("NAV")),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    items=item.get("items", []),
                )
                for item in data.get("navigation_structure", [])
            ],
            user_flows=[
                UIUXUserFlow(
                    id=item.get("id", uid("UF")),
                    name=item.get("name", ""),
                    actor=item.get("actor", ""),
                    steps=item.get("steps", []),
                    screens=item.get("screens", []),
                )
                for item in data.get("user_flows", [])
            ],
            screen_inventory=[
                ScreenItem(
                    id=item.get("id", uid("SCR")),
                    name=item.get("name", ""),
                    purpose=item.get("purpose", ""),
                    primary_actions=item.get("primary_actions", []),
                    layout_type=item.get("layout_type"),
                )
                for item in data.get("screen_inventory", [])
            ],
            page_hierarchy=[
                PageHierarchyItem(
                    id=item.get("id", uid("PG")),
                    name=item.get("name", ""),
                    parent_id=item.get("parent_id"),
                    level=item.get("level", 1),
                )
                for item in data.get("page_hierarchy", [])
            ],
            role_screen_mapping=[
                RoleScreenMapping(
                    role=item.get("role", ""),
                    screens=item.get("screens", []),
                    description=item.get("description"),
                )
                for item in data.get("role_screen_mapping", [])
            ],
            design_system=data.get("design_system") or {},
            component_inventory=[
                ComponentItem(
                    id=item.get("id", uid("CMP")),
                    name=item.get("name", ""),
                    category=item.get("category", "general"),
                    description=item.get("description", ""),
                    usage=item.get("usage"),
                )
                for item in data.get("component_inventory", [])
            ],
            frontend_handoff=data.get("frontend_handoff") or {},
            responsive_guidelines=data.get("responsive_guidelines", []),
            accessibility_guidelines=data.get("accessibility_guidelines", []),
        )
