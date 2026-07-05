"""Release reliability persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.release_reliability import (
    RrFreezeWindow,
    RrHealthGateResult,
    RrPromotionPolicy,
    RrPromotionRequest,
    RrReleaseReliability,
    RrRollbackRecord,
    RrRolloutOperation,
    RrVerificationRun,
)
from app.repositories.base import BaseRepository


class RrReleaseRepo(BaseRepository[RrReleaseReliability]):
    def __init__(self, session: AsyncSession):
        super().__init__(RrReleaseReliability, session)

    async def list_for_org(
        self, organization_id: str, *, status: str | None = None,
        offset: int = 0, limit: int = 50,
    ) -> tuple[list[RrReleaseReliability], int]:
        filters = [RrReleaseReliability.organization_id == organization_id]
        if status:
            filters.append(RrReleaseReliability.status == status.upper())
        stmt = select(RrReleaseReliability).where(*filters).order_by(
            RrReleaseReliability.created_at.desc(),
        ).offset(offset).limit(limit)
        rows = list((await self.session.execute(stmt)).scalars().all())
        total_stmt = select(RrReleaseReliability).where(*filters)
        total = len(list((await self.session.execute(total_stmt)).scalars().all()))
        return rows, total

    async def get_by_idempotency(self, organization_id: str, key: str) -> RrReleaseReliability | None:
        stmt = select(RrReleaseReliability).where(
            RrReleaseReliability.organization_id == organization_id,
            RrReleaseReliability.idempotency_key == key,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class RrVerificationRepo(BaseRepository[RrVerificationRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(RrVerificationRun, session)

    async def list_for_reliability(self, reliability_id: str) -> list[RrVerificationRun]:
        stmt = select(RrVerificationRun).where(
            RrVerificationRun.reliability_id == reliability_id,
        ).order_by(RrVerificationRun.started_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())


class RrHealthGateRepo(BaseRepository[RrHealthGateResult]):
    def __init__(self, session: AsyncSession):
        super().__init__(RrHealthGateResult, session)

    async def latest_for_reliability(self, reliability_id: str) -> RrHealthGateResult | None:
        stmt = select(RrHealthGateResult).where(
            RrHealthGateResult.reliability_id == reliability_id,
        ).order_by(RrHealthGateResult.evaluated_at.desc()).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_reliability(self, reliability_id: str) -> list[RrHealthGateResult]:
        stmt = select(RrHealthGateResult).where(
            RrHealthGateResult.reliability_id == reliability_id,
        ).order_by(RrHealthGateResult.evaluated_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())


class RrRolloutRepo(BaseRepository[RrRolloutOperation]):
    def __init__(self, session: AsyncSession):
        super().__init__(RrRolloutOperation, session)

    async def list_for_reliability(self, reliability_id: str) -> list[RrRolloutOperation]:
        stmt = select(RrRolloutOperation).where(
            RrRolloutOperation.reliability_id == reliability_id,
        ).order_by(RrRolloutOperation.created_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())


class RrPromotionPolicyRepo(BaseRepository[RrPromotionPolicy]):
    def __init__(self, session: AsyncSession):
        super().__init__(RrPromotionPolicy, session)

    async def list_for_org(self, organization_id: str) -> list[RrPromotionPolicy]:
        stmt = select(RrPromotionPolicy).where(RrPromotionPolicy.organization_id == organization_id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_policy(self, organization_id: str, source: str, target: str) -> RrPromotionPolicy | None:
        stmt = select(RrPromotionPolicy).where(
            RrPromotionPolicy.organization_id == organization_id,
            RrPromotionPolicy.source_tier == source.upper(),
            RrPromotionPolicy.target_tier == target.upper(),
            RrPromotionPolicy.enabled.is_(True),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class RrPromotionRequestRepo(BaseRepository[RrPromotionRequest]):
    def __init__(self, session: AsyncSession):
        super().__init__(RrPromotionRequest, session)

    async def list_queue(self, organization_id: str, *, status: str | None = None) -> list[RrPromotionRequest]:
        filters = [RrPromotionRequest.organization_id == organization_id]
        if status:
            filters.append(RrPromotionRequest.status == status.upper())
        stmt = select(RrPromotionRequest).where(*filters).order_by(RrPromotionRequest.created_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())


class RrFreezeWindowRepo(BaseRepository[RrFreezeWindow]):
    def __init__(self, session: AsyncSession):
        super().__init__(RrFreezeWindow, session)

    async def list_for_org(self, organization_id: str) -> list[RrFreezeWindow]:
        stmt = select(RrFreezeWindow).where(RrFreezeWindow.organization_id == organization_id)
        return list((await self.session.execute(stmt)).scalars().all())


class RrRollbackRepo(BaseRepository[RrRollbackRecord]):
    def __init__(self, session: AsyncSession):
        super().__init__(RrRollbackRecord, session)

    async def list_for_reliability(self, reliability_id: str) -> list[RrRollbackRecord]:
        stmt = select(RrRollbackRecord).where(
            RrRollbackRecord.reliability_id == reliability_id,
        ).order_by(RrRollbackRecord.created_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_for_org(self, organization_id: str) -> list[RrRollbackRecord]:
        stmt = select(RrRollbackRecord).where(
            RrRollbackRecord.organization_id == organization_id,
        ).order_by(RrRollbackRecord.created_at.desc()).limit(100)
        return list((await self.session.execute(stmt)).scalars().all())
