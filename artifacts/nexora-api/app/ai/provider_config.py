"""Per-organization AI provider/routing configuration service (Sprint 61D)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.routing import RoutingPolicy
from app.models.ai_platform import AIProviderConfig
from app.repositories.audit import AuditLogRepository


class ProviderConfigError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ProviderConfigService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditLogRepository(session)

    async def get(self, organization_id: str) -> AIProviderConfig | None:
        return await self.session.scalar(
            select(AIProviderConfig).where(
                AIProviderConfig.organization_id == organization_id)
        )

    async def upsert(
        self, *, organization_id: str, routing_policy: str | None = None,
        enabled_providers: list[str] | None = None,
        preferred_models: list[list[str]] | None = None,
        default_temperature: float | None = None, default_max_tokens: int | None = None,
        cache_enabled: bool | None = None, actor_user_id: str | None = None,
    ) -> AIProviderConfig:
        if routing_policy is not None:
            try:
                RoutingPolicy(routing_policy)
            except ValueError as exc:
                raise ProviderConfigError(
                    f"Invalid routing policy: {routing_policy}") from exc

        config = await self.get(organization_id)
        if config is None:
            config = AIProviderConfig(organization_id=organization_id)
            self.session.add(config)
        if routing_policy is not None:
            config.routing_policy = routing_policy
        if enabled_providers is not None:
            config.enabled_providers = enabled_providers
        if preferred_models is not None:
            config.preferred_models = preferred_models
        if default_temperature is not None:
            config.default_temperature = default_temperature
        if default_max_tokens is not None:
            config.default_max_tokens = default_max_tokens
        if cache_enabled is not None:
            config.cache_enabled = cache_enabled
        config.updated_by = actor_user_id
        await self.session.flush()
        await self.audit.log(
            action="ai_provider_config.updated", resource_type="ai_provider_config",
            resource_id=config.id, organization_id=organization_id, user_id=actor_user_id,
            details={"routing_policy": config.routing_policy},
        )
        return config
