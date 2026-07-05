"""Per-organization incident notification channel configuration."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_core import ConfigScope
from app.platform.config import ConfigService

SLACK_WEBHOOK_KEY = "incident_notifications.slack_webhook_url"
TEAMS_WEBHOOK_KEY = "incident_notifications.teams_webhook_url"
PAGERDUTY_ROUTING_KEY = "incident_notifications.pagerduty_routing_key"
DEFAULT_CHANNELS_KEY = "incident_notifications.default_channels"


def _mask_url(url: str | None) -> str | None:
    if not url:
        return None
    if len(url) <= 12:
        return "***"
    return f"{url[:8]}…{url[-4:]}"


class OrgNotificationChannelService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.config = ConfigService(session)

    async def get_channels(self, organization_id: str) -> dict:
        slack = await self.config.get(SLACK_WEBHOOK_KEY, organization_id=organization_id)
        teams = await self.config.get(TEAMS_WEBHOOK_KEY, organization_id=organization_id)
        pd_key = await self.config.get(PAGERDUTY_ROUTING_KEY, organization_id=organization_id)
        default_channels = await self.config.get(
            DEFAULT_CHANNELS_KEY, organization_id=organization_id, default=["slack", "email"],
        )
        return {
            "slack_webhook_configured": bool(slack),
            "teams_webhook_configured": bool(teams),
            "pagerduty_routing_configured": bool(pd_key),
            "slack_webhook_preview": _mask_url(slack),
            "teams_webhook_preview": _mask_url(teams),
            "default_channels": list(default_channels or ["slack", "email"]),
            "env_fallback": {
                "slack": False,
                "teams": False,
            },
        }

    async def set_channels(
        self,
        organization_id: str,
        *,
        updated_by: str | None,
        slack_webhook_url: str | None = None,
        teams_webhook_url: str | None = None,
        pagerduty_routing_key: str | None = None,
        default_channels: list[str] | None = None,
        clear_slack: bool = False,
        clear_teams: bool = False,
        clear_pagerduty: bool = False,
    ) -> dict:
        scope = ConfigScope.ORGANIZATION.value
        if clear_slack:
            await self.config.delete(SLACK_WEBHOOK_KEY, scope=scope, scope_id=organization_id)
        elif slack_webhook_url:
            await self.config.set(
                key=SLACK_WEBHOOK_KEY, value=slack_webhook_url.strip(),
                scope=scope, scope_id=organization_id, updated_by=updated_by,
            )
        if clear_teams:
            await self.config.delete(TEAMS_WEBHOOK_KEY, scope=scope, scope_id=organization_id)
        elif teams_webhook_url:
            await self.config.set(
                key=TEAMS_WEBHOOK_KEY, value=teams_webhook_url.strip(),
                scope=scope, scope_id=organization_id, updated_by=updated_by,
            )
        if clear_pagerduty:
            await self.config.delete(PAGERDUTY_ROUTING_KEY, scope=scope, scope_id=organization_id)
        elif pagerduty_routing_key:
            await self.config.set(
                key=PAGERDUTY_ROUTING_KEY, value=pagerduty_routing_key.strip(),
                scope=scope, scope_id=organization_id, updated_by=updated_by,
            )
        if default_channels is not None:
            await self.config.set(
                key=DEFAULT_CHANNELS_KEY, value=default_channels,
                scope=scope, scope_id=organization_id, updated_by=updated_by,
            )
        return await self.get_channels(organization_id)

    async def resolve_slack_webhook(self, organization_id: str) -> str | None:
        from app.core.config import settings

        org_url = await self.config.get(SLACK_WEBHOOK_KEY, organization_id=organization_id)
        if org_url:
            return str(org_url)
        return settings.SLACK_WEBHOOK_URL or None

    async def resolve_teams_webhook(self, organization_id: str) -> str | None:
        from app.core.config import settings

        org_url = await self.config.get(TEAMS_WEBHOOK_KEY, organization_id=organization_id)
        if org_url:
            return str(org_url)
        return settings.TEAMS_WEBHOOK_URL or None

    async def resolve_pagerduty_routing_key(self, organization_id: str) -> str | None:
        org_key = await self.config.get(PAGERDUTY_ROUTING_KEY, organization_id=organization_id)
        return str(org_key) if org_key else None

    async def resolve_pagerduty_api_key(self, organization_id: str) -> str | None:
        return None
