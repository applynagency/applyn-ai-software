"""Unified activity feed (Sprint 62A).

A single activity timeline for the whole platform, populated from domain events.
Queryable per organization, per actor (user), and per resource (object).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_core import ActivityEntry, DomainEvent
from app.platform.events import subscribe

# Human-readable verbs derived from event types (best-effort).
_VERBS = {
    "IncidentCreated": "created an incident",
    "IncidentResolved": "resolved an incident",
    "DeploymentCompleted": "completed a deployment",
    "DiscoveryFinished": "finished a discovery scan",
    "WorkflowCompleted": "completed a workflow",
    "UserInvited": "invited a user",
    "OrganizationCreated": "created an organization",
    "SubscriptionChanged": "changed the subscription",
    "CopilotCompleted": "completed a copilot session",
    "AgentRunCompleted": "completed an agent run",
    "PluginInstalled": "installed a plugin",
    "OpsDailyBriefing": "generated the daily operations briefing",
    "OpsShiftHandover": "generated a shift handover",
    "OpsMaintenanceScheduled": "scheduled maintenance",
    "EnvironmentCreated": "created an environment",
    "ProvisionStarted": "started cluster provisioning",
    "ProvisionCompleted": "completed cluster provisioning",
    "TerraformPlanGenerated": "generated a Terraform plan",
    "TerraformApplied": "applied Terraform changes",
    "TerraformDriftDetected": "detected infrastructure drift",
    "PlatformTemplateCreated": "created a platform template",
    "SecretRotated": "rotated a secret reference",
}


def _verb_for(event_type: str) -> str:
    return _VERBS.get(event_type, event_type)


class ActivityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        *,
        event_type: str,
        organization_id: str | None = None,
        actor_id: str | None = None,
        verb: str | None = None,
        object_type: str | None = None,
        object_id: str | None = None,
        summary: str = "",
        meta: dict | None = None,
    ) -> ActivityEntry:
        entry = ActivityEntry(
            event_type=event_type,
            organization_id=organization_id,
            actor_id=actor_id,
            verb=verb or _verb_for(event_type),
            object_type=object_type,
            object_id=object_id,
            summary=summary or _verb_for(event_type),
            meta=meta or {},
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def list(
        self,
        *,
        organization_id: str | None = None,
        actor_id: str | None = None,
        object_type: str | None = None,
        object_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ActivityEntry]:
        stmt = select(ActivityEntry)
        if organization_id is not None:
            stmt = stmt.where(ActivityEntry.organization_id == organization_id)
        if actor_id is not None:
            stmt = stmt.where(ActivityEntry.actor_id == actor_id)
        if object_type is not None:
            stmt = stmt.where(ActivityEntry.object_type == object_type)
        if object_id is not None:
            stmt = stmt.where(ActivityEntry.object_id == object_id)
        stmt = stmt.order_by(ActivityEntry.created_at.desc()).limit(limit).offset(offset)
        return list((await self.session.execute(stmt)).scalars().all())


async def activity_event_handler(session: AsyncSession, event: DomainEvent) -> None:
    """Domain-event subscriber that mirrors every event into the activity feed."""
    payload = event.payload or {}
    summary = payload.get("summary") or _verb_for(event.event_type)
    await ActivityService(session).record(
        event_type=event.event_type,
        organization_id=event.organization_id,
        actor_id=event.actor_id,
        object_type=event.aggregate_type,
        object_id=event.aggregate_id,
        summary=summary,
        meta=payload,
    )


# Mirror EVERY domain event into the activity feed.
subscribe("*", activity_event_handler)
