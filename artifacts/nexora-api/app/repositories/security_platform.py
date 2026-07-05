"""Enterprise Security Platform persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security_platform import (
    SecAccessReviewCampaign,
    SecBackfillJob,
    SecException,
    SecFinding,
    SecInvestigation,
    SecPostureSnapshot,
    SecProvider,
    SecRemediationExecution,
    SecRemediationProposal,
    SecSbomComponent,
    SecSbomRef,
    SecScanRun,
    SecSlaPolicy,
)
from app.repositories.base import BaseRepository


class SecFindingRepo(BaseRepository[SecFinding]):
    def __init__(self, session: AsyncSession):
        super().__init__(SecFinding, session)

    async def list_for_org(
        self, organization_id: str, *, status: str | None = None, severity: str | None = None,
        source: str | None = None, limit: int = 100, offset: int = 0,
    ) -> tuple[list[SecFinding], int]:
        filters = [SecFinding.organization_id == organization_id]
        if status:
            filters.append(SecFinding.status == status.upper())
        if severity:
            filters.append(SecFinding.severity == severity.upper())
        if source:
            filters.append(SecFinding.source == source.upper())
        stmt = select(SecFinding).where(*filters).order_by(SecFinding.created_at.desc())
        rows = list((await self.session.execute(stmt.offset(offset).limit(limit))).scalars().all())
        total_stmt = select(SecFinding).where(*filters)
        total = len(list((await self.session.execute(total_stmt)).scalars().all()))
        return rows, total

    async def get_by_fingerprint(self, organization_id: str, fingerprint: str) -> SecFinding | None:
        stmt = select(SecFinding).where(
            SecFinding.organization_id == organization_id,
            SecFinding.fingerprint == fingerprint,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_source_record(
        self, organization_id: str, source_system: str, source_record_id: str,
    ) -> SecFinding | None:
        stmt = select(SecFinding).where(
            SecFinding.organization_id == organization_id,
            SecFinding.source_system == source_system,
            SecFinding.source_record_id == source_record_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_open_for_gate(self, organization_id: str, *, limit: int = 200) -> list[SecFinding]:
        stmt = select(SecFinding).where(
            SecFinding.organization_id == organization_id,
            SecFinding.status.in_(("OPEN", "ACKNOWLEDGED", "IN_REMEDIATION")),
        ).order_by(SecFinding.created_at.desc()).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())


class SecScanRunRepo(BaseRepository[SecScanRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(SecScanRun, session)

    async def list_for_org(self, organization_id: str, *, limit: int = 50, offset: int = 0) -> tuple[list[SecScanRun], int]:
        stmt = select(SecScanRun).where(
            SecScanRun.organization_id == organization_id,
        ).order_by(SecScanRun.created_at.desc()).offset(offset).limit(limit)
        rows = list((await self.session.execute(stmt)).scalars().all())
        total = len(list((await self.session.execute(
            select(SecScanRun).where(SecScanRun.organization_id == organization_id),
        )).scalars().all()))
        return rows, total


class SecSbomRepo(BaseRepository[SecSbomRef]):
    def __init__(self, session: AsyncSession):
        super().__init__(SecSbomRef, session)

    async def list_for_org(self, organization_id: str) -> list[SecSbomRef]:
        stmt = select(SecSbomRef).where(SecSbomRef.organization_id == organization_id).order_by(SecSbomRef.created_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())


class SecExceptionRepo(BaseRepository[SecException]):
    def __init__(self, session: AsyncSession):
        super().__init__(SecException, session)

    async def list_for_org(self, organization_id: str) -> list[SecException]:
        stmt = select(SecException).where(SecException.organization_id == organization_id).order_by(SecException.created_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())


class SecRemediationRepo(BaseRepository[SecRemediationProposal]):
    def __init__(self, session: AsyncSession):
        super().__init__(SecRemediationProposal, session)

    async def list_for_org(self, organization_id: str, *, status: str | None = None) -> list[SecRemediationProposal]:
        filters = [SecRemediationProposal.organization_id == organization_id]
        if status:
            filters.append(SecRemediationProposal.status == status.upper())
        stmt = select(SecRemediationProposal).where(*filters).order_by(SecRemediationProposal.created_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())


class SecPostureRepo(BaseRepository[SecPostureSnapshot]):
    def __init__(self, session: AsyncSession):
        super().__init__(SecPostureSnapshot, session)

    async def latest(self, organization_id: str) -> SecPostureSnapshot | None:
        stmt = select(SecPostureSnapshot).where(
            SecPostureSnapshot.organization_id == organization_id,
        ).order_by(SecPostureSnapshot.created_at.desc()).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_org(self, organization_id: str, *, limit: int = 30) -> list[SecPostureSnapshot]:
        stmt = select(SecPostureSnapshot).where(
            SecPostureSnapshot.organization_id == organization_id,
        ).order_by(SecPostureSnapshot.created_at.desc()).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())


class SecInvestigationRepo(BaseRepository[SecInvestigation]):
    def __init__(self, session: AsyncSession):
        super().__init__(SecInvestigation, session)

    async def list_for_org(self, organization_id: str) -> list[SecInvestigation]:
        stmt = select(SecInvestigation).where(
            SecInvestigation.organization_id == organization_id,
        ).order_by(SecInvestigation.created_at.desc()).limit(50)
        return list((await self.session.execute(stmt)).scalars().all())


class SecAccessReviewRepo(BaseRepository[SecAccessReviewCampaign]):
    def __init__(self, session: AsyncSession):
        super().__init__(SecAccessReviewCampaign, session)

    async def list_for_org(self, organization_id: str) -> list[SecAccessReviewCampaign]:
        stmt = select(SecAccessReviewCampaign).where(
            SecAccessReviewCampaign.organization_id == organization_id,
        ).order_by(SecAccessReviewCampaign.created_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())


class SecProviderRepo(BaseRepository[SecProvider]):
    def __init__(self, session: AsyncSession):
        super().__init__(SecProvider, session)

    async def list_for_org(self, organization_id: str) -> list[SecProvider]:
        stmt = select(SecProvider).where(SecProvider.organization_id == organization_id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_type(self, organization_id: str, provider_type: str) -> SecProvider | None:
        stmt = select(SecProvider).where(
            SecProvider.organization_id == organization_id,
            SecProvider.provider_type == provider_type.upper(),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class SecSbomComponentRepo(BaseRepository[SecSbomComponent]):
    def __init__(self, session: AsyncSession):
        super().__init__(SecSbomComponent, session)

    async def list_for_org(
        self, organization_id: str, *, limit: int = 100, offset: int = 0,
    ) -> tuple[list[SecSbomComponent], int]:
        stmt = select(SecSbomComponent).where(
            SecSbomComponent.organization_id == organization_id,
        ).order_by(SecSbomComponent.name).offset(offset).limit(limit)
        rows = list((await self.session.execute(stmt)).scalars().all())
        total = len(list((await self.session.execute(
            select(SecSbomComponent).where(SecSbomComponent.organization_id == organization_id),
        )).scalars().all()))
        return rows, total

    async def get_by_normalized_key(self, organization_id: str, key: str) -> SecSbomComponent | None:
        stmt = select(SecSbomComponent).where(
            SecSbomComponent.organization_id == organization_id,
            SecSbomComponent.normalized_key == key,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class SecBackfillJobRepo(BaseRepository[SecBackfillJob]):
    def __init__(self, session: AsyncSession):
        super().__init__(SecBackfillJob, session)

    async def latest_for_org(self, organization_id: str) -> SecBackfillJob | None:
        stmt = select(SecBackfillJob).where(
            SecBackfillJob.organization_id == organization_id,
        ).order_by(SecBackfillJob.created_at.desc()).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()


class SecSlaPolicyRepo(BaseRepository[SecSlaPolicy]):
    def __init__(self, session: AsyncSession):
        super().__init__(SecSlaPolicy, session)

    async def list_for_org(self, organization_id: str) -> list[SecSlaPolicy]:
        stmt = select(SecSlaPolicy).where(SecSlaPolicy.organization_id == organization_id)
        return list((await self.session.execute(stmt)).scalars().all())


class SecRemediationExecutionRepo(BaseRepository[SecRemediationExecution]):
    def __init__(self, session: AsyncSession):
        super().__init__(SecRemediationExecution, session)

    async def get_by_proposal(self, organization_id: str, proposal_id: str) -> SecRemediationExecution | None:
        stmt = select(SecRemediationExecution).where(
            SecRemediationExecution.organization_id == organization_id,
            SecRemediationExecution.proposal_id == proposal_id,
        ).order_by(SecRemediationExecution.created_at.desc()).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()
