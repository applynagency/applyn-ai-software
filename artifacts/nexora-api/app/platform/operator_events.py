"""AI Platform Operator event handler (Sprint 64B).

Subscribes to domain events — no polling where events already exist.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.platform.events import DomainEventType, subscribe
from app.services.ai_operator import AIOperatorService

logger = get_logger(__name__)

_OPERATOR_TRIGGERS = {
    DomainEventType.INCIDENT_CREATED.value,
    DomainEventType.INCIDENT_RESOLVED.value,
    DomainEventType.DEPLOYMENT_FAILED.value,
    DomainEventType.DEPLOYMENT_SUCCEEDED.value,
    DomainEventType.PIPELINE_COMPLETED.value,
    DomainEventType.TERRAFORM_APPLIED.value,
    DomainEventType.TERRAFORM_DRIFT_DETECTED.value,
    DomainEventType.PROVISION_COMPLETED.value,
    DomainEventType.OPS_DAILY_BRIEFING.value,
}


async def operator_event_handler(session: AsyncSession, event) -> None:
    if not settings.AI_OPERATOR_ENABLED:
        return
    if not event.organization_id:
        return
    if event.event_type not in _OPERATOR_TRIGGERS:
        return
    try:
        await AIOperatorService(session).analyze_for_org(
            event.organization_id, trigger=event.event_type,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("operator_event_handler_failed", event=event.event_type, error=str(exc))


if settings.AI_OPERATOR_ENABLED:
    subscribe("*", operator_event_handler)
