"""Periodic pipeline sync for verified marketplace CI/CD connections."""

from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.models.integration import ConnectionStatus, IntegrationConnection
from app.models.organization import OrganizationMember, OrganizationRole
from app.models.user import User
from app.services.integration_capabilities import supports_pipeline_sync
from app.services.integration_sync import IntegrationSyncService

logger = structlog.get_logger(__name__)


class IntegrationPipelineSchedulerRunner:
    async def run_once(self, session: AsyncSession) -> dict:
        stmt = select(IntegrationConnection).where(
            IntegrationConnection.credential_id.isnot(None),
            IntegrationConnection.status.in_([
                ConnectionStatus.VERIFIED.value,
                ConnectionStatus.CONNECTED.value,
            ]),
        )
        connections = list((await session.execute(stmt)).scalars().all())
        synced = 0
        skipped = 0
        errors = 0

        for conn in connections:
            key = (conn.integration_key or "").upper()
            if not supports_pipeline_sync(key):
                skipped += 1
                continue
            actor = await self._owner_actor(session, conn.organization_id)
            if actor is None:
                skipped += 1
                continue
            user, org_context = actor
            try:
                await IntegrationSyncService(session).sync_connection(
                    user, org_context, conn.id, sync_runs=True,
                )
                synced += 1
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                errors += 1
                logger.info(
                    "integration_pipeline_sync_skipped",
                    connection_id=conn.id, provider=key, error=type(exc).__name__,
                )
                await session.rollback()

        if synced:
            await session.commit()
        return {"synced": synced, "skipped": skipped, "errors": errors}

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
        return user, OrgContext(
            user=user, organization_id=organization_id, role=OrganizationRole.OWNER,
        )


async def integration_pipeline_loop() -> None:
    """Background loop: sync pipeline runs from verified CI/CD connections."""
    from app.core.config import settings
    from app.database.session import AsyncSessionLocal
    from app.observability.tracing import start_as_current_span
    from app.redis.locks import scheduler_lock

    runner = IntegrationPipelineSchedulerRunner()
    interval = max(60, settings.JOB_CRON_INTEGRATION_PIPELINE_SYNC_SECONDS)
    logger.info("integration_pipeline_scheduler_started", interval_seconds=interval)

    while True:
        try:
            async with scheduler_lock("integration_pipeline") as token:
                if token is not None:
                    with start_as_current_span("scheduler.integration_pipeline", kind="consumer"):
                        async with AsyncSessionLocal() as session:
                            result = await runner.run_once(session)
                            if result.get("synced"):
                                logger.info("integration_pipeline_scheduler_tick", **result)
        except asyncio.CancelledError:
            logger.info("integration_pipeline_scheduler_stopped")
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("integration_pipeline_scheduler_tick_failed", error=str(exc))
        await asyncio.sleep(interval)
