import json
import re
import uuid

import anthropic

from app.backend_v1.prompt_builder import BackendDeveloperV1PromptBuilder
from app.core.config import settings
from app.core.exceptions import AgentError
from app.core.logging import get_logger
from app.schemas.backend_v1 import (
    ApiSpecification,
    AuthenticationSpecifications,
    AuthorizationSpecifications,
    BackendDeveloperV1Output,
    BackgroundJobSpecification,
    DatabaseModelSpecification,
    IntegrationSpecification,
    ModuleBreakdownItem,
    RepositorySpecification,
    ServiceSpecification,
    UserRoleSpecification,
    ValidationSpecification,
)

logger = get_logger(__name__)


class BackendDeveloperV1Agent:
    def __init__(self):
        if not settings.ANTHROPIC_API_KEY:
            raise AgentError("ANTHROPIC_API_KEY is not configured. Add it in the Secrets panel.")
        from app.ai.compat import gateway_anthropic_client

        self.client = gateway_anthropic_client(feature="agent:backend_v1")
        self.prompt_builder = BackendDeveloperV1PromptBuilder()

    async def run(
        self,
        *,
        requirement_text: str,
        backend_architect_output: dict,
    ) -> tuple[BackendDeveloperV1Output, int]:
        logger.info("backend_v1_agent_start", requirement_length=len(requirement_text))

        user_prompt = self.prompt_builder.build_user_prompt(
            requirement_text=requirement_text,
            backend_architect_output=backend_architect_output,
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
            "backend_v1_agent_complete",
            tokens_used=tokens_used,
            services=len(output.service_specifications),
        )
        return output, tokens_used

    def _parse_output(self, data: dict) -> BackendDeveloperV1Output:
        def uid(prefix: str) -> str:
            return f"{prefix}-{str(uuid.uuid4())[:6]}"

        auth_data = data.get("authentication_specifications") or {}
        authz_data = data.get("authorization_specifications") or {}

        return BackendDeveloperV1Output(
            service_specifications=[
                ServiceSpecification(
                    id=item.get("id") or uid("SVC"),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    responsibilities=item.get("responsibilities") or [],
                    dependencies=item.get("dependencies") or [],
                )
                for item in data.get("service_specifications") or []
            ],
            repository_specifications=[
                RepositorySpecification(
                    id=item.get("id") or uid("REPO"),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    entity=item.get("entity"),
                    methods=item.get("methods") or [],
                )
                for item in data.get("repository_specifications") or []
            ],
            api_specifications=[
                ApiSpecification(
                    id=item.get("id") or uid("API"),
                    method=item.get("method", "GET"),
                    path=item.get("path", "/"),
                    description=item.get("description", ""),
                    service=item.get("service"),
                    auth_required=item.get("auth_required", True),
                )
                for item in data.get("api_specifications") or []
            ],
            database_model_specifications=[
                DatabaseModelSpecification(
                    id=item.get("id") or uid("MODEL"),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    table_name=item.get("table_name"),
                    fields=item.get("fields") or [],
                    relationships=item.get("relationships") or [],
                )
                for item in data.get("database_model_specifications") or []
            ],
            authentication_specifications=AuthenticationSpecifications(
                strategy=auth_data.get("strategy"),
                token_type=auth_data.get("token_type"),
                providers=auth_data.get("providers") or [],
                middleware=auth_data.get("middleware") or [],
            ),
            authorization_specifications=AuthorizationSpecifications(
                model=authz_data.get("model"),
                roles=[
                    UserRoleSpecification(
                        id=role.get("id") or uid("ROLE"),
                        name=role.get("name", ""),
                        description=role.get("description", ""),
                        permissions=role.get("permissions") or [],
                    )
                    for role in authz_data.get("roles") or []
                ],
                policies=authz_data.get("policies") or [],
            ),
            validation_specifications=[
                ValidationSpecification(
                    id=item.get("id") or uid("VAL"),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    scope=item.get("scope"),
                )
                for item in data.get("validation_specifications") or []
            ],
            background_job_specifications=[
                BackgroundJobSpecification(
                    id=item.get("id") or uid("JOB"),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    schedule=item.get("schedule"),
                    queue=item.get("queue"),
                )
                for item in data.get("background_job_specifications") or []
            ],
            integration_specifications=[
                IntegrationSpecification(
                    id=item.get("id") or uid("INT"),
                    name=item.get("name", ""),
                    type=item.get("type", "external"),
                    description=item.get("description", ""),
                )
                for item in data.get("integration_specifications") or []
            ],
            folder_structure=data.get("folder_structure") or {},
            module_breakdown=[
                ModuleBreakdownItem(
                    id=item.get("id") or uid("MOD"),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    services=item.get("services") or [],
                    repositories=item.get("repositories") or [],
                )
                for item in data.get("module_breakdown") or []
            ],
            implementation_guidelines=data.get("implementation_guidelines") or [],
        )
