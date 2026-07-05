"""Integrations Health Board — unified multi-tool status for operations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError
from app.models.incident import MonitoringAlert, MonitoringAlertStatus
from app.models.user import User
from app.repositories.incident import MonitoringAlertRepository
from app.repositories.integration import IntegrationConnectionRepository
from app.services.integration_capabilities import enrichment_for
from app.tenancy.permissions import can_read_resources


class IntegrationHealthBoardService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.connections = IntegrationConnectionRepository(session)
        self.alerts = MonitoringAlertRepository(session)

    def _ensure_read(self, user: User, org_context: OrgContext) -> str:
        if not can_read_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    async def list_board(self, user: User, org_context: OrgContext) -> list[dict]:
        organization_id = self._ensure_read(user, org_context)
        since = datetime.now(UTC) - timedelta(hours=24)
        conns = await self.connections.list_for_org(organization_id)
        recent, _ = await self.alerts.list_for_org(organization_id, limit=500)
        alerts_by_provider: dict[str, dict[str, int]] = {}
        for alert in recent:
            if alert.last_seen_at and alert.last_seen_at < since:
                continue
            key = (alert.provider or "").upper()
            bucket = alerts_by_provider.setdefault(key, {"total": 0, "firing": 0})
            bucket["total"] += 1
            if alert.status == MonitoringAlertStatus.FIRING.value:
                bucket["firing"] += 1

        board: list[dict] = []
        for c in conns:
            key = (c.integration_key or "").upper()
            enrich = enrichment_for(key)
            alerts = alerts_by_provider.get(key, {"total": 0, "firing": 0})
            board.append({
                "connection_id": c.id,
                "integration_key": key,
                "name": c.name,
                "status": c.status,
                "health": c.health,
                "readiness_score": c.readiness_score,
                "live_data": enrich["live_data"],
                "pipeline_sync": enrich["pipeline_sync"],
                "gitops_sync": enrich.get("gitops_sync", False),
                "discovery": enrich["discovery"],
                "alert_ingest": enrich["alert_ingest"],
                "last_sync_at": c.last_sync_at,
                "last_verified_at": c.last_verified_at,
                "alerts_24h": alerts["total"],
                "firing_alerts": alerts["firing"],
                "permissions_granted": c.permissions_granted or [],
            })
        return board
