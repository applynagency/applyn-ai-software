import json
import re
import uuid

import anthropic

from app.business_analyst.prompt_builder import BusinessAnalystPromptBuilder
from app.core.config import settings
from app.core.exceptions import AgentError
from app.core.logging import get_logger
from app.schemas.business_analyst import (
    AcceptanceCriterion,
    ApiRequirement,
    AssumptionItem,
    BusinessAnalystOutput,
    BusinessRule,
    DependencyItem,
    EntityDefinition,
    FunctionalRequirement,
    ModuleDefinition,
    NonFunctionalRequirement,
    PermissionDefinition,
    RiskItem,
    RoleDefinition,
    UserFlow,
)

logger = get_logger(__name__)


class BusinessAnalystAgent:
    def __init__(self):
        if not settings.ANTHROPIC_API_KEY:
            raise AgentError("ANTHROPIC_API_KEY is not configured. Add it in the Secrets panel.")
        from app.ai.compat import gateway_anthropic_client

        self.client = gateway_anthropic_client(feature="agent:business_analyst")
        self.prompt_builder = BusinessAnalystPromptBuilder()

    async def run(
        self,
        *,
        requirement_text: str,
        product_owner_output: dict,
    ) -> tuple[BusinessAnalystOutput, int]:
        logger.info("business_analyst_agent_start", requirement_length=len(requirement_text))

        user_prompt = self.prompt_builder.build_user_prompt(
            requirement_text=requirement_text,
            product_owner_output=product_owner_output,
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
            "business_analyst_agent_complete",
            tokens_used=tokens_used,
            functional_requirements=len(output.functional_requirements),
        )
        return output, tokens_used

    def _parse_output(self, data: dict) -> BusinessAnalystOutput:
        def uid(prefix: str) -> str:
            return f"{prefix}-{str(uuid.uuid4())[:6]}"

        return BusinessAnalystOutput(
            project_summary=data.get("project_summary") or {},
            functional_requirements=[
                FunctionalRequirement(
                    id=item.get("id", uid("FR")),
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    priority=item.get("priority", "medium"),
                    module=item.get("module"),
                )
                for item in data.get("functional_requirements", [])
            ],
            non_functional_requirements=[
                NonFunctionalRequirement(
                    id=item.get("id", uid("NFR")),
                    category=item.get("category", "general"),
                    description=item.get("description", ""),
                    metric=item.get("metric"),
                )
                for item in data.get("non_functional_requirements", [])
            ],
            roles=[
                RoleDefinition(
                    id=item.get("id", uid("ROLE")),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                )
                for item in data.get("roles", [])
            ],
            permissions=[
                PermissionDefinition(
                    id=item.get("id", uid("PERM")),
                    role=item.get("role", ""),
                    resource=item.get("resource", ""),
                    action=item.get("action", ""),
                    description=item.get("description", ""),
                )
                for item in data.get("permissions", [])
            ],
            modules=[
                ModuleDefinition(
                    id=item.get("id", uid("MOD")),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    dependencies=item.get("dependencies", []),
                )
                for item in data.get("modules", [])
            ],
            business_rules=[
                BusinessRule(
                    id=item.get("id", uid("BR")),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    module=item.get("module"),
                )
                for item in data.get("business_rules", [])
            ],
            entities=[
                EntityDefinition(
                    id=item.get("id", uid("ENT")),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    attributes=item.get("attributes", []),
                )
                for item in data.get("entities", [])
            ],
            user_flows=[
                UserFlow(
                    id=item.get("id", uid("UF")),
                    name=item.get("name", ""),
                    actor=item.get("actor", ""),
                    steps=item.get("steps", []),
                )
                for item in data.get("user_flows", [])
            ],
            api_requirements=[
                ApiRequirement(
                    id=item.get("id", uid("API")),
                    method=item.get("method", "GET"),
                    path=item.get("path", "/"),
                    description=item.get("description", ""),
                    module=item.get("module"),
                )
                for item in data.get("api_requirements", [])
            ],
            acceptance_criteria=[
                AcceptanceCriterion(
                    id=item.get("id", uid("AC")),
                    requirement_id=item.get("requirement_id", ""),
                    description=item.get("description", ""),
                    testable=item.get("testable", True),
                )
                for item in data.get("acceptance_criteria", [])
            ],
            assumptions=[
                AssumptionItem(
                    id=item.get("id", uid("ASM")),
                    description=item.get("description", ""),
                    impact=item.get("impact", "medium"),
                )
                for item in data.get("assumptions", [])
            ],
            risks=[
                RiskItem(
                    id=item.get("id", uid("RISK")),
                    description=item.get("description", ""),
                    impact=item.get("impact", "medium"),
                    mitigation=item.get("mitigation"),
                )
                for item in data.get("risks", [])
            ],
            dependencies=[
                DependencyItem(
                    id=item.get("id", uid("DEP")),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    type=item.get("type", "internal"),
                )
                for item in data.get("dependencies", [])
            ],
        )
