"""Data archival / retention strategy (Sprint 62B).

Tables that grow unbounded under production load (processed domain events,
terminal jobs, search query logs) need a retention story so the hot tables stay
small and queries stay fast. This service purges rows older than the configured
window. It is conservative — only fully-processed/terminal rows are eligible, so
in-flight work and the audit trail (which has its own retention) are untouched.

Designed to be driven by a daily cron; idempotent and bounded per run.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.database.base import utcnow

logger = get_logger(__name__)


class ArchiveService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def archive_events(self, *, retention_days: int | None = None,
                             batch: int = 1000) -> int:
        """Purge processed/dead-letter domain events older than the window."""
        from app.models.platform_core import DomainEvent, EventStatus

        days = retention_days if retention_days is not None else (
            settings.ARCHIVE_EVENT_RETENTION_DAYS)
        if not days:
            return 0
        cutoff = utcnow() - timedelta(days=days)
        ids = list((await self.session.execute(
            select(DomainEvent.id).where(
                DomainEvent.status.in_(
                    (EventStatus.PROCESSED.value, EventStatus.DEAD_LETTER.value)),
                DomainEvent.created_at < cutoff,
            ).limit(batch))).scalars().all())
        if not ids:
            return 0
        await self.session.execute(delete(DomainEvent).where(DomainEvent.id.in_(ids)))
        await self.session.commit()
        return len(ids)

    async def archive_search_logs(self, *, retention_days: int = 90,
                                  batch: int = 5000) -> int:
        from app.models.platform_core import SearchQueryLog

        cutoff = utcnow() - timedelta(days=retention_days)
        ids = list((await self.session.execute(
            select(SearchQueryLog.id).where(
                SearchQueryLog.created_at < cutoff).limit(batch))).scalars().all())
        if not ids:
            return 0
        await self.session.execute(
            delete(SearchQueryLog).where(SearchQueryLog.id.in_(ids)))
        await self.session.commit()
        return len(ids)

    async def run(self) -> dict:
        """Run the full archive sweep; returns per-table counts."""
        events = await self.archive_events()
        # Jobs cleanup reuses the execution engine's dead-run retention.
        from app.platform.execution import ExecutionEngine

        jobs = await ExecutionEngine(self.session).cleanup_dead()
        logs = await self.archive_search_logs()
        result = {"events": events, "jobs": jobs, "search_logs": logs}
        logger.info("archive_run", **result)
        return result
