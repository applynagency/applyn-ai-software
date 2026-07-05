import json
import re
import uuid

import anthropic

from app.backend_architect.prompt_builder import BackendArchitectPromptBuilder
from app.core.config import settings
from app.core.exceptions import AgentError
from app.core.logging import get_logger
from app.schemas.backend_architect import (
    ApiDefinition,
    AuthenticationArchitecture,
    AuthorizationArchitecture,
    BackendArchitectOutput,
    DatabaseEntity,
    IntegrationDefinition,
    SecurityArchitecture,
    SecurityControl,
    ServiceDefinition,
    UserRole,
)

logger = get_logger(__name__)


class BackendArchitectAgent:
    def __init__(self):
        if not settings.ANTHROPIC_API_KEY:
            raise AgentError("ANTHROPIC_API_KEY is not configured. Add it in the Secrets panel.")
        from app.ai.compat import gateway_anthropic_client

        self.client = gateway_anthropic_client(feature="agent:backend_architect")
        self.prompt_builder = BackendArchitectPromptBuilder()

    async def run(
        self,
        *,
        requirement_text: str,
        business_analyst_output: dict,
    ) -> tuple[BackendArchitectOutput, int]:
        logger.info("backend_architect_agent_start", requirement_length=len(requirement_text))

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
            "backend_architect_agent_complete",
            tokens_used=tokens_used,
            apis=len(output.api_architecture),
        )
        return output, tokens_used

    def _parse_output(self, data: dict) -> BackendArchitectOutput:
        def uid(prefix: str) -> str:
            return f"{prefix}-{str(uuid.uuid4())[:6]}"

        auth_data = data.get("authentication_architecture") or {}
        authz_data = data.get("authorization_architecture") or {}
        sec_data = data.get("security_architecture") or {}

        return BackendArchitectOutput(
            backend_stack=data.get("backend_stack") or {},
            service_architecture=[
                ServiceDefinition(
                    id=item.get("id") or uid("SVC"),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    responsibilities=item.get("responsibilities") or [],
                )
                for item in data.get("service_architecture") or []
            ],
            api_architecture=[
                ApiDefinition(
                    id=item.get("id") or uid("API"),
                    method=item.get("method", "GET"),
                    path=item.get("path", "/"),
                    description=item.get("description", ""),
                    service=item.get("service"),
                    auth_required=item.get("auth_required", True),
                )
                for item in data.get("api_architecture") or []
            ],
            database_architecture=[
                DatabaseEntity(
                    id=item.get("id") or uid("DB"),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    tables=item.get("tables") or [],
                    relationships=item.get("relationships") or [],
                )
                for item in data.get("database_architecture") or []
            ],
            authentication_architecture=AuthenticationArchitecture(
                strategy=auth_data.get("strategy"),
                token_type=auth_data.get("token_type"),
                providers=auth_data.get("providers") or [],
                session_management=auth_data.get("session_management"),
            ),
            authorization_architecture=AuthorizationArchitecture(
                model=authz_data.get("model"),
                roles=[
                    UserRole(
                        id=role.get("id") or uid("ROLE"),
                        name=role.get("name", ""),
                        description=role.get("description", ""),
                        permissions=role.get("permissions") or [],
                    )
                    for role in authz_data.get("roles") or []
                ],
                policies=authz_data.get("policies") or [],
            ),
            integration_architecture=[
                IntegrationDefinition(
                    id=item.get("id") or uid("INT"),
                    name=item.get("name", ""),
                    type=item.get("type", "external"),
                    description=item.get("description", ""),
                )
                for item in data.get("integration_architecture") or []
            ],
            caching_architecture=data.get("caching_architecture") or {},
            event_architecture=data.get("event_architecture") or {},
            deployment_architecture=data.get("deployment_architecture") or {},
            folder_structure=data.get("folder_structure") or {},
            security_architecture=SecurityArchitecture(
                controls=[
                    SecurityControl(
                        id=ctrl.get("id") or uid("SEC"),
                        name=ctrl.get("name", ""),
                        description=ctrl.get("description", ""),
                        category=ctrl.get("category"),
                    )
                    for ctrl in sec_data.get("controls") or []
                ],
                compliance=sec_data.get("compliance") or [],
                threat_mitigations=sec_data.get("threat_mitigations") or [],
            ),
            development_guidelines=data.get("development_guidelines") or [],
        )
