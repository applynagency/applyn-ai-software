"""Platform Engineering persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_engineering import (
    PECatalogItem,
    PECatalogRequest,
    PEComplianceReport,
    PEDriftFinding,
    PEEnvironment,
    PEGoldenTemplate,
    PEIacRepository,
    PEIacRun,
    PEIacStack,
    PEPlatformTemplate,
    PEProvisionRun,
    PESecretReference,
)
from app.repositories.base import BaseRepository


class PEIacRepositoryRepo(BaseRepository[PEIacRepository]):
    def __init__(self, session: AsyncSession):
        super().__init__(PEIacRepository, session)

    async def list_for_org(self, organization_id: str) -> list[PEIacRepository]:
        items, _ = await self.list_all(
            filters=[PEIacRepository.organization_id == organization_id], limit=200,
        )
        return items


class PEIacStackRepo(BaseRepository[PEIacStack]):
    def __init__(self, session: AsyncSession):
        super().__init__(PEIacStack, session)

    async def list_for_org(self, organization_id: str) -> list[PEIacStack]:
        items, _ = await self.list_all(
            filters=[PEIacStack.organization_id == organization_id], limit=200,
        )
        return items


class PEIacRunRepo(BaseRepository[PEIacRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(PEIacRun, session)

    async def list_for_stack(self, stack_id: str) -> list[PEIacRun]:
        stmt = (
            select(PEIacRun).where(PEIacRun.stack_id == stack_id)
            .order_by(PEIacRun.created_at.desc()).limit(50)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_for_org(self, organization_id: str) -> list[PEIacRun]:
        stmt = (
            select(PEIacRun).where(PEIacRun.organization_id == organization_id)
            .order_by(PEIacRun.created_at.desc()).limit(100)
        )
        return list((await self.session.execute(stmt)).scalars().all())


class PEPlatformTemplateRepo(BaseRepository[PEPlatformTemplate]):
    def __init__(self, session: AsyncSession):
        super().__init__(PEPlatformTemplate, session)

    async def list_for_org(self, organization_id: str) -> list[PEPlatformTemplate]:
        items, _ = await self.list_all(
            filters=[PEPlatformTemplate.organization_id == organization_id], limit=100,
        )
        return items


class PEEnvironmentRepo(BaseRepository[PEEnvironment]):
    def __init__(self, session: AsyncSession):
        super().__init__(PEEnvironment, session)

    async def list_for_org(self, organization_id: str) -> list[PEEnvironment]:
        items, _ = await self.list_all(
            filters=[PEEnvironment.organization_id == organization_id], limit=100,
        )
        return items


class PEProvisionRunRepo(BaseRepository[PEProvisionRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(PEProvisionRun, session)

    async def list_for_org(self, organization_id: str) -> list[PEProvisionRun]:
        stmt = (
            select(PEProvisionRun).where(PEProvisionRun.organization_id == organization_id)
            .order_by(PEProvisionRun.created_at.desc()).limit(100)
        )
        return list((await self.session.execute(stmt)).scalars().all())


class PESecretRefRepo(BaseRepository[PESecretReference]):
    def __init__(self, session: AsyncSession):
        super().__init__(PESecretReference, session)

    async def list_for_org(self, organization_id: str) -> list[PESecretReference]:
        items, _ = await self.list_all(
            filters=[PESecretReference.organization_id == organization_id], limit=200,
        )
        return items


class PECatalogItemRepo(BaseRepository[PECatalogItem]):
    def __init__(self, session: AsyncSession):
        super().__init__(PECatalogItem, session)

    async def list_for_org(self, organization_id: str) -> list[PECatalogItem]:
        items, _ = await self.list_all(
            filters=[PECatalogItem.organization_id == organization_id, PECatalogItem.is_active.is_(True)],
            limit=100,
        )
        return items


class PECatalogRequestRepo(BaseRepository[PECatalogRequest]):
    def __init__(self, session: AsyncSession):
        super().__init__(PECatalogRequest, session)

    async def list_for_org(self, organization_id: str) -> list[PECatalogRequest]:
        stmt = (
            select(PECatalogRequest).where(PECatalogRequest.organization_id == organization_id)
            .order_by(PECatalogRequest.created_at.desc()).limit(100)
        )
        return list((await self.session.execute(stmt)).scalars().all())


class PEGoldenTemplateRepo(BaseRepository[PEGoldenTemplate]):
    def __init__(self, session: AsyncSession):
        super().__init__(PEGoldenTemplate, session)

    async def list_for_org(self, organization_id: str) -> list[PEGoldenTemplate]:
        items, _ = await self.list_all(
            filters=[PEGoldenTemplate.organization_id == organization_id], limit=100,
        )
        return items


class PEComplianceReportRepo(BaseRepository[PEComplianceReport]):
    def __init__(self, session: AsyncSession):
        super().__init__(PEComplianceReport, session)

    async def latest(self, organization_id: str) -> PEComplianceReport | None:
        stmt = (
            select(PEComplianceReport).where(PEComplianceReport.organization_id == organization_id)
            .order_by(PEComplianceReport.created_at.desc()).limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class PEDriftFindingRepo(BaseRepository[PEDriftFinding]):
    def __init__(self, session: AsyncSession):
        super().__init__(PEDriftFinding, session)

    async def list_active(self, organization_id: str) -> list[PEDriftFinding]:
        stmt = (
            select(PEDriftFinding).where(
                PEDriftFinding.organization_id == organization_id,
                PEDriftFinding.acknowledged.is_(False),
            ).order_by(PEDriftFinding.created_at.desc()).limit(100)
        )
        return list((await self.session.execute(stmt)).scalars().all())
