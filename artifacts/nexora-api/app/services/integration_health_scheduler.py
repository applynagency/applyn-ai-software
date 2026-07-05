"""Periodic integration health checks (Sprint 65G)."""

from __future__ import annotations

import asyncio
import random

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.config import settings
from app.models.integration_readiness import IntConnectionRegistry
from app.models.organization import OrganizationMember, OrganizationRole
from app.models.user import User
from app.services.integration_readiness import IntegrationReadinessService

logger = structlog.get_logger(__name__)


class IntegrationHealthSchedulerRunner:
    async def run_once(self, session: AsyncSession) -> int:
        org_ids = await self._orgs_with_registry(session)
        validated = 0
        for organization_id in org_ids:
            actor = await self._owner_actor(session, organization_id)
            if actor is None:
                continue
            user, org_context = actor
            svc = IntegrationReadinessService(session)
            try:
                await svc.sync_registry(organization_id)
                rows = await session.execute(
                    select(IntConnectionRegistry).where(
                        IntConnectionRegistry.organization_id == organization_id,
                        IntConnectionRegistry.lifecycle_state.in_(
                            ("CONNECTED", "DEGRADED", "FAILED", "REAUTH_REQUIRED"),
                        ),
                    ),
                )
                for row in rows.scalars().all():
                    jitter = random.uniform(0, 2.0)  # noqa: S311
                    await asyncio.sleep(jitter)
                    await svc.validate_connection(user, org_context, row.id)
                    validated += 1
                await svc.process_expiry_warnings(organization_id)
                await session.commit()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover
                logger.error(
                    "integration_health_org_failed",
                    organization_id=organization_id,
                    error=str(exc),
                )
                await session.rollback()
        return validated

    async def _orgs_with_registry(self, session: AsyncSession) -> list[str]:
        stmt = select(IntConnectionRegistry.organization_id).distinct()
        return list((await session.execute(stmt)).scalars().all())

    async def _owner_actor(
        self, session: AsyncSession, organization_id: str,
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
        return user, OrgContext(user=user, organization_id=organization_id, role=OrganizationRole.OWNER)


async def integration_health_loop() -> None:
    from app.database.session import AsyncSessionLocal
    from app.observability.tracing import start_as_current_span
    from app.redis.locks import scheduler_lock

    runner = IntegrationHealthSchedulerRunner()
    interval = max(60, getattr(settings, "INTEGRATION_HEALTH_INTERVAL_SECONDS", 300))
    logger.info("integration_health_scheduler_started", interval_seconds=interval)

    while True:
        try:
            async with scheduler_lock("integration_health") as token:
                if token is not None:
                    with start_as_current_span("scheduler.integration_health", kind="consumer"):
                        async with AsyncSessionLocal() as session:
                            count = await runner.run_once(session)
                            if count:
                                logger.info("integration_health_scheduler_tick", validated=count)
        except asyncio.CancelledError:
            logger.info("integration_health_scheduler_stopped")
            raise
        except Exception as exc:  # pragma: no cover
            logger.error("integration_health_scheduler_tick_failed", error=str(exc))
        await asyncio.sleep(interval)
