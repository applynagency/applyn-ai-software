"""Quota resolution + enforcement (Sprint 61C).

Effective limit precedence: per-org override > plan limit. A check yields a
:class:`QuotaDecision` describing hard/soft/grace/warning state. ``enforce``
raises :class:`QuotaExceeded` when a hard limit is breached (unless the plan's
policy is ``soft`` or global enforcement is disabled).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.billing import Plan, QuotaOverride, SubscriptionStatus, UsageMetric
from app.services.billing.metering import MeteringService
from app.services.billing.subscriptions import SubscriptionService

UNLIMITED = -1


@dataclass
class QuotaDecision:
    metric: str
    limit: int            # -1 = unlimited
    used: int
    requested: int
    allowed: bool
    warning: bool         # at/over the warning threshold
    soft: bool            # over soft threshold but under hard limit
    over_hard: bool       # would exceed the hard limit
    enforcement: str      # "hard" | "soft"
    remaining: int        # max(limit - used, 0); -1 when unlimited
    reason: str | None = None

    def as_dict(self) -> dict:
        return {
            "metric": self.metric, "limit": self.limit, "used": self.used,
            "requested": self.requested, "allowed": self.allowed,
            "warning": self.warning, "soft": self.soft, "over_hard": self.over_hard,
            "enforcement": self.enforcement, "remaining": self.remaining,
            "reason": self.reason,
        }


class QuotaExceeded(Exception):
    def __init__(self, decision: QuotaDecision) -> None:
        super().__init__(f"Quota exceeded for {decision.metric}")
        self.decision = decision
        self.status_code = 402  # Payment Required


class QuotaService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.metering = MeteringService(session)
        self.subscriptions = SubscriptionService(session)

    async def _override(self, organization_id: str, metric_value: str) -> int | None:
        ov = await self.session.scalar(
            select(QuotaOverride).where(
                QuotaOverride.organization_id == organization_id,
                QuotaOverride.metric == metric_value,
            )
        )
        return ov.limit_value if ov else None

    async def effective_limit(self, organization_id: str, metric: UsageMetric | str) -> int:
        metric_value = metric.value if isinstance(metric, UsageMetric) else metric
        override = await self._override(organization_id, metric_value)
        if override is not None:
            return override
        plan = await self.subscriptions.plan_for(organization_id)
        limits = plan.limits or {}
        return int(limits.get(metric_value, UNLIMITED))

    async def check(
        self, organization_id: str, metric: UsageMetric | str, amount: int = 1,
    ) -> QuotaDecision:
        metric_value = metric.value if isinstance(metric, UsageMetric) else metric
        plan = await self.subscriptions.plan_for(organization_id)
        policy = plan.quota_policy or {}
        enforcement = policy.get("enforcement", "hard")
        soft_ratio = float(policy.get("soft_ratio", 0.8))
        warning_ratio = float(policy.get("warning_ratio", 0.9))

        limit = await self.effective_limit(organization_id, metric_value)
        usage = await self.metering.current_usage(organization_id)
        used = usage.get(metric_value, 0)
        projected = used + amount

        if limit == UNLIMITED:
            return QuotaDecision(
                metric=metric_value, limit=UNLIMITED, used=used, requested=amount,
                allowed=True, warning=False, soft=False, over_hard=False,
                enforcement=enforcement, remaining=UNLIMITED,
            )

        over_hard = projected > limit
        soft = (not over_hard) and projected >= limit * soft_ratio
        warning = projected >= limit * warning_ratio
        remaining = max(limit - used, 0)

        # Subscription state can independently block operations.
        sub = await self.subscriptions.get_or_create(organization_id)
        blocked_state = not self.subscriptions.is_operational(sub)

        allowed = True
        reason = None
        if blocked_state:
            allowed = False
            reason = f"subscription_{sub.status.lower()}"
        elif over_hard:
            if enforcement == "hard" and settings.BILLING_QUOTA_ENFORCEMENT:
                # Grace state still permits operation.
                if sub.status == SubscriptionStatus.GRACE.value:
                    allowed = True
                    reason = "grace"
                else:
                    allowed = False
                    reason = "hard_limit_exceeded"
            else:
                allowed = True
                reason = "soft_enforcement"

        return QuotaDecision(
            metric=metric_value, limit=limit, used=used, requested=amount,
            allowed=allowed, warning=warning, soft=soft, over_hard=over_hard,
            enforcement=enforcement, remaining=remaining, reason=reason,
        )

    async def enforce(
        self, organization_id: str, metric: UsageMetric | str, amount: int = 1,
    ) -> QuotaDecision:
        """Check and raise QuotaExceeded if not allowed. Emits an event on breach."""
        decision = await self.check(organization_id, metric, amount)
        if decision.over_hard:
            await self._emit_exceeded(organization_id, decision)
        if not decision.allowed:
            raise QuotaExceeded(decision)
        return decision

    async def meter(
        self, organization_id: str, metric: UsageMetric | str, amount: int = 1,
        *, enforce: bool = True,
    ) -> QuotaDecision:
        """Enforce (optional) then record usage. The common one-call helper."""
        decision = (
            await self.enforce(organization_id, metric, amount)
            if enforce else await self.check(organization_id, metric, amount)
        )
        await self.metering.record(organization_id, metric, amount)
        return decision

    async def set_override(
        self, organization_id: str, metric: UsageMetric | str, limit_value: int,
        *, note: str | None = None, actor_user_id: str | None = None,
    ) -> QuotaOverride:
        from app.repositories.audit import AuditLogRepository

        metric_value = metric.value if isinstance(metric, UsageMetric) else metric
        existing = await self.session.scalar(
            select(QuotaOverride).where(
                QuotaOverride.organization_id == organization_id,
                QuotaOverride.metric == metric_value,
            )
        )
        if existing is not None:
            existing.limit_value = limit_value
            existing.note = note
            ov = existing
        else:
            ov = QuotaOverride(
                organization_id=organization_id, metric=metric_value,
                limit_value=limit_value, note=note, created_by=actor_user_id,
            )
            self.session.add(ov)
        await self.session.flush()
        await AuditLogRepository(self.session).log(
            action="quota.override_set", resource_type="quota_override",
            resource_id=ov.id, organization_id=organization_id, user_id=actor_user_id,
            details={"metric": metric_value, "limit": limit_value},
        )
        return ov

    async def _emit_exceeded(self, organization_id: str, decision: QuotaDecision) -> None:
        from app.services.billing.webhooks import BillingWebhookService

        await BillingWebhookService(self.session).emit(
            organization_id, "quota.exceeded", decision.as_dict()
        )

    async def all_decisions(self, organization_id: str) -> list[QuotaDecision]:
        """A check for every metric (used by the usage dashboard)."""
        out = []
        for metric in UsageMetric:
            out.append(await self.check(organization_id, metric, 0))
        return out


# Re-export for callers that build limit maps.
def plan_limit(plan: Plan, metric: UsageMetric | str) -> int:
    metric_value = metric.value if isinstance(metric, UsageMetric) else metric
    return int((plan.limits or {}).get(metric_value, UNLIMITED))
