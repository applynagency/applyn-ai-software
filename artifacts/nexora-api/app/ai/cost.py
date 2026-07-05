"""AI cost + token accounting (Sprint 61D).

Records one ``ai_usage_records`` row per gateway call and aggregates token / cost
/ latency / cache-hit-ratio per organization and per feature.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.types import LLMResponse
from app.models.ai_platform import AIUsageRecord


def _now() -> datetime:
    return datetime.now(UTC)


class CostTracker:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self, *, organization_id: str | None, feature: str, response: LLMResponse,
        status: str = "success",
    ) -> AIUsageRecord:
        rec = AIUsageRecord(
            organization_id=organization_id, feature=feature,
            provider=response.provider, model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cost_usd=response.cost_usd, latency_ms=response.latency_ms,
            cache_hit=response.cached, status=status,
        )
        self.session.add(rec)
        await self.session.flush()
        return rec

    async def summary(
        self, organization_id: str | None, *, days: int = 30,
        by_feature: bool = False,
    ) -> dict:
        since = _now() - timedelta(days=days)
        group = AIUsageRecord.feature if by_feature else AIUsageRecord.provider
        cache_hit_sum = func.coalesce(
            func.sum(case((AIUsageRecord.cache_hit.is_(True), 1), else_=0)), 0)
        stmt = (
            select(
                group,
                func.coalesce(func.sum(AIUsageRecord.input_tokens), 0),
                func.coalesce(func.sum(AIUsageRecord.output_tokens), 0),
                func.coalesce(func.sum(AIUsageRecord.cost_usd), 0.0),
                func.coalesce(func.avg(AIUsageRecord.latency_ms), 0.0),
                func.count(AIUsageRecord.id),
                cache_hit_sum,
            )
            .where(AIUsageRecord.created_at >= since)
            .group_by(group)
        )
        if organization_id is not None:
            stmt = stmt.where(AIUsageRecord.organization_id == organization_id)

        breakdown = []
        total_tokens = 0
        total_cost = 0.0
        total_calls = 0
        total_cache_hits = 0
        for key, in_tok, out_tok, cost, avg_lat, calls, cache_hits in (
                await self.session.execute(stmt)).all():
            tok = int(in_tok) + int(out_tok)
            total_tokens += tok
            total_cost += float(cost or 0.0)
            total_calls += int(calls)
            total_cache_hits += int(cache_hits or 0)
            breakdown.append({
                "key": key, "input_tokens": int(in_tok), "output_tokens": int(out_tok),
                "tokens": tok, "cost_usd": round(float(cost or 0.0), 6),
                "avg_latency_ms": round(float(avg_lat or 0.0), 2), "calls": int(calls),
                "cache_hits": int(cache_hits or 0),
            })
        return {
            "organization_id": organization_id,
            "window_days": days,
            "grouped_by": "feature" if by_feature else "provider",
            "totals": {
                "tokens": total_tokens,
                "cost_usd": round(total_cost, 6),
                "calls": total_calls,
                "cache_hit_ratio": round(total_cache_hits / total_calls, 4) if total_calls else 0.0,
            },
            "breakdown": breakdown,
        }
