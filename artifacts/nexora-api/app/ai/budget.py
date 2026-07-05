"""Per-organization AI token budgeting (Sprint 62B).

Caps daily token spend per organization so a runaway feature or abusive tenant
cannot exhaust the AI budget for everyone. Aggregates today's tokens from the
durable ``ai_usage_records`` (written by :class:`~app.ai.cost.CostTracker`) and
reports remaining headroom. Enforcement is opt-in (``AI_TOKEN_BUDGET_ENABLED``)
so existing flows and tests are unaffected by default.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.ai_platform import AIUsageRecord


class BudgetExceededError(Exception):
    def __init__(self, used: int, budget: int) -> None:
        self.used = used
        self.budget = budget
        super().__init__(f"AI daily token budget exceeded: {used}/{budget}")


def _start_of_day() -> datetime:
    now = datetime.now(UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


class TokenBudget:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def used_today(self, organization_id: str | None) -> int:
        stmt = select(
            func.coalesce(func.sum(AIUsageRecord.input_tokens), 0)
            + func.coalesce(func.sum(AIUsageRecord.output_tokens), 0)
        ).where(AIUsageRecord.created_at >= _start_of_day())
        if organization_id is not None:
            stmt = stmt.where(AIUsageRecord.organization_id == organization_id)
        return int((await self.session.execute(stmt)).scalar() or 0)

    async def status(self, organization_id: str | None) -> dict:
        budget = int(settings.AI_DAILY_TOKEN_BUDGET or 0)
        used = await self.used_today(organization_id)
        remaining = max(0, budget - used) if budget else None
        return {
            "organization_id": organization_id,
            "enabled": bool(settings.AI_TOKEN_BUDGET_ENABLED and budget),
            "budget": budget,
            "used": used,
            "remaining": remaining,
            "exceeded": bool(budget) and used >= budget,
            "resets_at": (_start_of_day() + timedelta(days=1)).isoformat(),
        }

    async def check(self, organization_id: str | None) -> None:
        """Raise :class:`BudgetExceededError` when the org is over budget."""
        budget = int(settings.AI_DAILY_TOKEN_BUDGET or 0)
        if not (settings.AI_TOKEN_BUDGET_ENABLED and budget):
            return
        used = await self.used_today(organization_id)
        if used >= budget:
            raise BudgetExceededError(used, budget)
