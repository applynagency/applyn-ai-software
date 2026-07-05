"""AI platform background maintenance (Sprint 61D).

Called by cron jobs:

* ``evaluation_sweep``        — compute rolling evaluation aggregates (health KPI)
* ``consolidate_memory``      — prune low-importance, stale memory entries
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_platform import AIEvaluation, AIMemoryEntry, MemoryScope


def _now() -> datetime:
    return datetime.now(UTC)


class AIPlatformMaintenance:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def evaluation_sweep(self, *, days: int = 1) -> dict:
        since = _now() - timedelta(days=days)
        rows = (await self.session.execute(
            select(AIEvaluation.passed).where(AIEvaluation.created_at >= since)
        )).scalars().all()
        total = len(rows)
        passed = sum(1 for r in rows if r)
        return {"window_days": days, "evaluations": total, "passed": passed,
                "pass_rate": round(passed / total, 4) if total else 0.0}

    async def consolidate_memory(
        self, *, max_age_days: int = 90, min_importance: float = 0.2,
    ) -> dict:
        """Prune stale, low-importance semantic/episodic memory.

        Organization and user memory are retained (they are explicit facts).
        """
        cutoff = _now() - timedelta(days=max_age_days)
        stmt = delete(AIMemoryEntry).where(
            AIMemoryEntry.created_at < cutoff,
            AIMemoryEntry.importance < min_importance,
            AIMemoryEntry.scope.in_([MemoryScope.SEMANTIC.value, MemoryScope.EPISODIC.value]),
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return {"pruned": int(result.rowcount or 0), "cutoff": cutoff.isoformat()}
