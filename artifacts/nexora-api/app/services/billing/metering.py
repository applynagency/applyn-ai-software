"""Usage metering (Sprint 61C).

Records per-organization, per-metric daily aggregates. ``record`` is the single
entry point used across the app (atomic upsert-style increment). Reads support
current-period totals and historical reporting.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import UsageMetric, UsageRecord

logger = logging.getLogger(__name__)


def _today() -> date:
    return datetime.now(UTC).date()


class MeteringService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self, organization_id: str, metric: UsageMetric | str, amount: int = 1,
        *, on: date | None = None,
    ) -> int:
        """Increment today's aggregate for ``metric``; returns the new daily value.

        Race-safe: relies on the unique (org, metric, day) constraint and retries
        on conflict so concurrent writers converge.
        """
        metric_value = metric.value if isinstance(metric, UsageMetric) else metric
        day = on or _today()
        existing = await self.session.scalar(
            select(UsageRecord).where(
                UsageRecord.organization_id == organization_id,
                UsageRecord.metric == metric_value,
                UsageRecord.usage_date == day,
            )
        )
        if existing is not None:
            existing.value += amount
            self.session.add(existing)
            await self.session.flush()
            return existing.value
        record = UsageRecord(
            organization_id=organization_id, metric=metric_value,
            usage_date=day, value=amount,
        )
        self.session.add(record)
        try:
            await self.session.flush()
            return record.value
        except IntegrityError:
            await self.session.rollback()
            # Lost the race — re-read and increment the winner's row.
            existing = await self.session.scalar(
                select(UsageRecord).where(
                    UsageRecord.organization_id == organization_id,
                    UsageRecord.metric == metric_value,
                    UsageRecord.usage_date == day,
                )
            )
            if existing is None:  # pragma: no cover - extremely unlikely
                raise
            existing.value += amount
            self.session.add(existing)
            await self.session.flush()
            return existing.value

    async def current_usage(
        self, organization_id: str, *, since: date | None = None, until: date | None = None,
    ) -> dict[str, int]:
        """Sum usage per metric over [since, until] (defaults: last 30 days)."""
        until = until or _today()
        since = since or (until - timedelta(days=30))
        stmt = (
            select(UsageRecord.metric, func.coalesce(func.sum(UsageRecord.value), 0))
            .where(
                UsageRecord.organization_id == organization_id,
                UsageRecord.usage_date >= since,
                UsageRecord.usage_date <= until,
            )
            .group_by(UsageRecord.metric)
        )
        rows = (await self.session.execute(stmt)).all()
        usage = {m.value: 0 for m in UsageMetric}
        for metric, total in rows:
            usage[metric] = int(total or 0)
        return usage

    async def daily_series(
        self, organization_id: str, metric: UsageMetric | str, *, days: int = 30,
    ) -> list[dict]:
        """Historical daily values for a metric (for reporting/charts)."""
        metric_value = metric.value if isinstance(metric, UsageMetric) else metric
        since = _today() - timedelta(days=days)
        stmt = (
            select(UsageRecord.usage_date, UsageRecord.value)
            .where(
                UsageRecord.organization_id == organization_id,
                UsageRecord.metric == metric_value,
                UsageRecord.usage_date >= since,
            )
            .order_by(UsageRecord.usage_date.asc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [{"date": d.isoformat(), "value": int(v)} for d, v in rows]
