"""Sprint 42A — MonitoringScheduler.

A background loop that, on a fixed cadence (default 60s), runs the monitoring
cycle for every organization that has at least one connected monitoring
provider credential:

    poll providers → detect alerts → deduplicate → create incidents
        → trigger investigation → notify users

It mirrors the established Sprint 38B workflow-scheduler pattern (asyncio loop,
own session per tick, cancellation-aware). It acts as a synthetic OWNER of each
organization so the reused investigation engine's write-permission guard passes;
it still performs only read-only monitoring and approval-gated remediation is
never auto-executed.
"""

from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.config import settings
from app.models.organization import OrganizationMember, OrganizationRole
from app.models.user import User
from app.services.monitoring import MONITORING_PROVIDERS, MonitoringEngine
from app.services.integration_poll_sources import orgs_with_ingest_targets

logger = structlog.get_logger(__name__)


class MonitoringSchedulerRunner:
    """Stateless tick executed by the background loop (and by tests directly)."""

    async def run_once(self, session: AsyncSession) -> int:
        """Poll every organization that has a connected monitoring provider.

        Returns the number of organizations polled."""
        org_ids = await self._orgs_with_monitoring(session)
        polled = 0
        for organization_id in org_ids:
            actor = await self._owner_actor(session, organization_id)
            if actor is None:
                continue
            user, org_context = actor
            try:
                engine = MonitoringEngine(session)
                await engine.poll(user, org_context)
                polled += 1
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - defensive
                logger.error(
                    "monitoring_scheduler_org_failed",
                    organization_id=organization_id,
                    error=str(exc),
                )
                await session.rollback()
        return polled

    async def _orgs_with_monitoring(self, session: AsyncSession) -> list[str]:
        return await orgs_with_ingest_targets(session, MONITORING_PROVIDERS)

    async def _owner_actor(
        self, session: AsyncSession, organization_id: str
    ) -> tuple[User, OrgContext] | None:
        stmt = (
            select(OrganizationMember)
            .where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.role == OrganizationRole.OWNER,
            )
            .order_by(OrganizationMember.created_at.asc())
            .limit(1)
        )
        member = (await session.execute(stmt)).scalar_one_or_none()
        if member is None:
            return None
        user = await session.get(User, member.user_id)
        if user is None:
            return None
        return user, OrgContext(
            user=user, organization_id=organization_id, role=OrganizationRole.OWNER
        )


async def monitoring_loop() -> None:
    """Background loop: run the monitoring cycle on a fixed cadence."""
    from app.database.session import AsyncSessionLocal

    runner = MonitoringSchedulerRunner()
    interval = max(15, settings.MONITORING_INTERVAL_SECONDS)
    logger.info("monitoring_scheduler_started", interval_seconds=interval)
    from app.observability.tracing import start_as_current_span
    from app.redis.locks import scheduler_lock

    while True:
        try:
            async with scheduler_lock("monitoring") as token:
                if token is not None:
                    with start_as_current_span("scheduler.monitoring", kind="consumer"):
                        async with AsyncSessionLocal() as session:
                            polled = await runner.run_once(session)
                            if polled:
                                logger.info(
                                    "monitoring_scheduler_tick", organizations_polled=polled
                                )
        except asyncio.CancelledError:
            logger.info("monitoring_scheduler_stopped")
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("monitoring_scheduler_tick_failed", error=str(exc))
        await asyncio.sleep(interval)


async def escalation_loop() -> None:
    """Sprint 42B — advance unacknowledged incidents through their escalation
    ladder on a fixed cadence (runs across all organizations)."""
    from app.database.session import AsyncSessionLocal
    from app.services.oncall import EscalationEngine

    interval = max(15, settings.ESCALATION_INTERVAL_SECONDS)
    logger.info("escalation_scheduler_started", interval_seconds=interval)
    from app.observability.tracing import start_as_current_span
    from app.redis.locks import scheduler_lock

    while True:
        try:
            async with scheduler_lock("escalation") as token:
                if token is not None:
                    with start_as_current_span("scheduler.escalation", kind="consumer"):
                        async with AsyncSessionLocal() as session:
                            fired = await EscalationEngine(session).process_due()
                            if fired:
                                logger.info(
                                    "escalation_scheduler_tick", escalations_fired=fired
                                )
        except asyncio.CancelledError:
            logger.info("escalation_scheduler_stopped")
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("escalation_scheduler_tick_failed", error=str(exc))
        await asyncio.sleep(interval)
