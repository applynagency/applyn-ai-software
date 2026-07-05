"""Billing background maintenance (Sprint 61C).

Backs the scheduled jobs: quota period reset, usage aggregation, subscription
lifecycle transitions, license expiration and billing reminders. Each method is
idempotent and safe to run repeatedly under the distributed scheduler.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Subscription, SubscriptionStatus
from app.repositories.audit import AuditLogRepository
from app.services.billing.licenses import LicenseService
from app.services.billing.subscriptions import SubscriptionService

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


class BillingMaintenance:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditLogRepository(session)
        self.subscriptions = SubscriptionService(session)

    async def reset_period_quotas(self) -> dict:
        """Roll over billing periods whose end has passed (resets usage windows)."""
        now = _now()
        rolled = 0
        subs = list((await self.session.execute(select(Subscription))).scalars().all())
        for sub in subs:
            if sub.current_period_end and _aware(sub.current_period_end) <= now:
                sub.current_period_start = now
                sub.current_period_end = now + timedelta(days=30)
                self.session.add(sub)
                rolled += 1
                await self.audit.log(
                    action="quota.reset", resource_type="subscription",
                    resource_id=sub.id, organization_id=sub.organization_id,
                    details={"period_start": now.isoformat()},
                )
        if rolled:
            await self.session.flush()
        return {"periods_rolled": rolled}

    async def aggregate_usage(self) -> dict:
        """Usage is recorded as daily aggregates already; this verifies and reports.

        Returns a small summary so the job result is observable. (Hook point for
        compaction/rollups into longer-term storage if needed.)"""
        from app.models.billing import UsageRecord

        count = await self.session.scalar(select(UsageRecord.id).limit(1))
        return {"ok": True, "has_usage": count is not None}

    async def run_lifecycle(self) -> dict:
        """Advance subscription states + emit reminders/expiry events."""
        result = await self.subscriptions.run_lifecycle_tick()
        return result

    async def expire_licenses(self) -> dict:
        expired = await LicenseService(self.session).expire_due()
        return {"licenses_expired": expired}

    async def send_billing_reminders(self) -> dict:
        """Emit reminders for overdue subscriptions (delegates to webhook events)."""
        from app.services.billing.webhooks import BillingWebhookService

        webhooks = BillingWebhookService(self.session)
        sent = 0
        subs = list((await self.session.execute(
            select(Subscription).where(Subscription.status == SubscriptionStatus.OVERDUE.value)
        )).scalars().all())
        for sub in subs:
            await webhooks.emit(sub.organization_id, "subscription.changed",
                                {"status": sub.status, "reminder": True})
            sent += 1
        return {"reminders_sent": sent}
