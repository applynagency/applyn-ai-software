"""Subscription lifecycle (Sprint 61C).

One subscription per organization with an explicit state machine:
trial → active → (overdue → grace → suspended) / cancelled / expired.
Transitions are auditable and emit webhook events.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.billing import (
    BillingProviderType,
    Plan,
    Subscription,
    SubscriptionStatus,
)
from app.repositories.audit import AuditLogRepository
from app.services.billing.plans import PlanService


def _now() -> datetime:
    return datetime.now(UTC)


class SubscriptionError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class SubscriptionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditLogRepository(session)
        self.plans = PlanService(session)

    async def get(self, organization_id: str) -> Subscription | None:
        return await self.session.scalar(
            select(Subscription).where(Subscription.organization_id == organization_id)
        )

    async def get_or_create(self, organization_id: str) -> Subscription:
        sub = await self.get(organization_id)
        if sub is not None:
            return sub
        plan = await self.plans.get_by_slug(settings.BILLING_DEFAULT_PLAN_SLUG)
        if plan is None:
            await self.plans.seed_defaults()
            plan = await self.plans.get_by_slug(settings.BILLING_DEFAULT_PLAN_SLUG)
        if plan is None:
            raise SubscriptionError("No default plan configured", status_code=500)
        now = _now()
        trial_end = now + timedelta(days=plan.trial_days) if plan.trial_days else None
        sub = Subscription(
            organization_id=organization_id,
            plan_id=plan.id,
            status=(SubscriptionStatus.TRIAL.value if trial_end else SubscriptionStatus.ACTIVE.value),
            provider=BillingProviderType.MANUAL.value,
            trial_ends_at=trial_end,
            current_period_start=now,
            current_period_end=_period_end(now),
        )
        self.session.add(sub)
        await self.session.flush()
        await self.audit.log(
            action="subscription.created", resource_type="subscription",
            resource_id=sub.id, organization_id=organization_id,
            details={"plan": plan.slug, "status": sub.status},
        )
        return sub

    async def plan_for(self, organization_id: str) -> Plan:
        sub = await self.get_or_create(organization_id)
        plan = await self.session.get(Plan, sub.plan_id)
        if plan is None:  # pragma: no cover - FK guarantees presence
            raise SubscriptionError("Subscription plan missing", status_code=500)
        return plan

    async def assign_plan(
        self, organization_id: str, plan_id: str, *,
        provider: str | None = None, actor_user_id: str | None = None,
    ) -> Subscription:
        plan = await self.session.get(Plan, plan_id)
        if plan is None:
            raise SubscriptionError("Plan not found", status_code=404)
        sub = await self.get_or_create(organization_id)
        old_plan_id = sub.plan_id
        sub.plan_id = plan.id
        if provider:
            sub.provider = provider
        # Re-activate on (re)assignment unless cancelled/expired explicitly kept.
        if sub.status in (SubscriptionStatus.SUSPENDED.value, SubscriptionStatus.OVERDUE.value,
                          SubscriptionStatus.GRACE.value):
            sub.status = SubscriptionStatus.ACTIVE.value
        self.session.add(sub)
        await self.session.flush()
        await self.audit.log(
            action="subscription.plan_assigned", resource_type="subscription",
            resource_id=sub.id, organization_id=organization_id, user_id=actor_user_id,
            details={"old_plan_id": old_plan_id, "new_plan_id": plan.id, "plan": plan.slug},
        )
        await self._emit(organization_id, "subscription.changed",
                         {"plan": plan.slug, "status": sub.status})
        return sub

    async def transition(
        self, organization_id: str, status: SubscriptionStatus, *,
        actor_user_id: str | None = None, reason: str | None = None,
    ) -> Subscription:
        sub = await self.get_or_create(organization_id)
        prev = sub.status
        sub.status = status.value
        now = _now()
        if status == SubscriptionStatus.CANCELLED:
            sub.cancelled_at = now
        elif status == SubscriptionStatus.GRACE:
            plan = await self.session.get(Plan, sub.plan_id)
            grace_days = int((plan.quota_policy or {}).get("grace_days", 7)) if plan else 7
            sub.grace_until = now + timedelta(days=grace_days)
        self.session.add(sub)
        await self.session.flush()
        await self.audit.log(
            action=f"subscription.{status.value.lower()}", resource_type="subscription",
            resource_id=sub.id, organization_id=organization_id, user_id=actor_user_id,
            details={"from": prev, "to": status.value, "reason": reason},
        )
        await self._emit(organization_id, "subscription.changed",
                         {"status": status.value, "from": prev})
        return sub

    async def suspend(self, organization_id: str, *, actor_user_id: str | None = None,
                      reason: str | None = None) -> Subscription:
        return await self.transition(organization_id, SubscriptionStatus.SUSPENDED,
                                     actor_user_id=actor_user_id, reason=reason)

    async def resume(self, organization_id: str, *, actor_user_id: str | None = None) -> Subscription:
        return await self.transition(organization_id, SubscriptionStatus.ACTIVE,
                                     actor_user_id=actor_user_id, reason="resumed")

    def is_operational(self, sub: Subscription) -> bool:
        """Whether the org may perform metered operations under its current state."""
        if sub.status in (SubscriptionStatus.ACTIVE.value, SubscriptionStatus.TRIAL.value,
                          SubscriptionStatus.GRACE.value, SubscriptionStatus.OVERDUE.value):
            return True
        return False

    async def run_lifecycle_tick(self) -> dict:
        """Auto-transition subscriptions whose dates have elapsed. Returns counts.

        trial expired      -> OVERDUE (payment required) and emit trial.ending done
        grace expired       -> SUSPENDED
        cancel_at reached   -> CANCELLED
        """
        now = _now()
        counts = {"trial_expired": 0, "grace_expired": 0, "cancelled": 0, "trial_ending": 0}
        subs = list((await self.session.execute(select(Subscription))).scalars().all())
        for sub in subs:
            if (sub.status == SubscriptionStatus.TRIAL.value and sub.trial_ends_at
                    and _aware(sub.trial_ends_at) <= now):
                sub.status = SubscriptionStatus.OVERDUE.value
                counts["trial_expired"] += 1
                await self.audit.log(
                    action="subscription.overdue", resource_type="subscription",
                    resource_id=sub.id, organization_id=sub.organization_id,
                    details={"reason": "trial_expired"},
                )
                await self._emit(sub.organization_id, "trial.ending",
                                 {"trial_ends_at": sub.trial_ends_at.isoformat()})
            elif (sub.status == SubscriptionStatus.TRIAL.value and sub.trial_ends_at
                  and _aware(sub.trial_ends_at) - now <= timedelta(days=3)):
                counts["trial_ending"] += 1
                await self._emit(sub.organization_id, "trial.ending",
                                 {"trial_ends_at": sub.trial_ends_at.isoformat()})
            if (sub.status == SubscriptionStatus.GRACE.value and sub.grace_until
                    and _aware(sub.grace_until) <= now):
                sub.status = SubscriptionStatus.SUSPENDED.value
                counts["grace_expired"] += 1
                await self.audit.log(
                    action="subscription.suspended", resource_type="subscription",
                    resource_id=sub.id, organization_id=sub.organization_id,
                    details={"reason": "grace_expired"},
                )
                await self._emit(sub.organization_id, "subscription.changed",
                                 {"status": "SUSPENDED", "reason": "grace_expired"})
            if (sub.cancel_at and _aware(sub.cancel_at) <= now
                    and sub.status != SubscriptionStatus.CANCELLED.value):
                sub.status = SubscriptionStatus.CANCELLED.value
                sub.cancelled_at = now
                counts["cancelled"] += 1
                await self.audit.log(
                    action="subscription.cancelled", resource_type="subscription",
                    resource_id=sub.id, organization_id=sub.organization_id,
                    details={"reason": "cancel_at_reached"},
                )
            self.session.add(sub)
        await self.session.flush()
        return counts

    async def _emit(self, organization_id: str, event_type: str, payload: dict) -> None:
        from app.services.billing.webhooks import BillingWebhookService

        await BillingWebhookService(self.session).emit(organization_id, event_type, payload)


def _period_end(start: datetime) -> datetime:
    # Approximate monthly period (30 days) — providers override with real dates.
    return start + timedelta(days=30)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
