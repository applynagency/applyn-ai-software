"""Organization usage dashboard (Sprint 61C).

Aggregates current usage, plan limits, remaining quota, projected end-of-period
usage and overages into a single payload for the org dashboard API.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import UsageMetric
from app.services.billing.metering import MeteringService
from app.services.billing.quota import UNLIMITED, QuotaService
from app.services.billing.subscriptions import SubscriptionService


def _now() -> datetime:
    return datetime.now(UTC)


class UsageDashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.subscriptions = SubscriptionService(session)
        self.metering = MeteringService(session)
        self.quota = QuotaService(session)

    async def snapshot(self, organization_id: str) -> dict:
        sub = await self.subscriptions.get_or_create(organization_id)
        plan = await self.subscriptions.plan_for(organization_id)

        period_start = sub.current_period_start
        period_end = sub.current_period_end
        usage = await self.metering.current_usage(
            organization_id,
            since=period_start.date() if period_start else None,
        )

        # Linear projection to end of billing period.
        elapsed_frac = _period_fraction(period_start, period_end)

        metrics_out = []
        overages = []
        for metric in UsageMetric:
            mv = metric.value
            used = usage.get(mv, 0)
            limit = await self.quota.effective_limit(organization_id, metric)
            remaining = UNLIMITED if limit == UNLIMITED else max(limit - used, 0)
            projected = used if elapsed_frac <= 0 else int(used / elapsed_frac)
            over = limit != UNLIMITED and used > limit
            metrics_out.append({
                "metric": mv,
                "used": used,
                "limit": limit,
                "remaining": remaining,
                "projected_end_of_period": projected,
                "over_limit": over,
                "utilization": (round(used / limit, 4) if limit not in (UNLIMITED, 0) else 0.0),
            })
            if over:
                overages.append({"metric": mv, "used": used, "limit": limit,
                                 "overage": used - limit})

        return {
            "organization_id": organization_id,
            "plan": {
                "id": plan.id, "slug": plan.slug, "name": plan.name,
                "tier": plan.tier, "support_tier": plan.support_tier,
            },
            "subscription": {
                "status": sub.status,
                "provider": sub.provider,
                "trial_ends_at": sub.trial_ends_at.isoformat() if sub.trial_ends_at else None,
                "current_period_start": period_start.isoformat() if period_start else None,
                "current_period_end": period_end.isoformat() if period_end else None,
                "grace_until": sub.grace_until.isoformat() if sub.grace_until else None,
            },
            "metrics": metrics_out,
            "overages": overages,
            "features": plan.features or {},
        }


def _period_fraction(start, end) -> float:
    if not start or not end:
        return 1.0
    start = start if start.tzinfo else start.replace(tzinfo=UTC)
    end = end if end.tzinfo else end.replace(tzinfo=UTC)
    total = (end - start).total_seconds()
    if total <= 0:
        return 1.0
    elapsed = (_now() - start).total_seconds()
    return max(0.0, min(1.0, elapsed / total))
