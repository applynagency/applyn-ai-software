"""Enterprise Incident Response Platform persistence."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.incident_response import (
    IrCommunication,
    IrCommunicationTemplate,
    IrCoordinatorRun,
    IrMajorIncident,
    IrScheduleOverride,
    IrStatusComponent,
    IrStatusIncident,
    IrStatusPage,
    IrStatusSubscriber,
)
from app.repositories.base import BaseRepository


class IrScheduleOverrideRepo(BaseRepository[IrScheduleOverride]):
    def __init__(self, session: AsyncSession):
        super().__init__(IrScheduleOverride, session)

    async def list_for_schedule(self, organization_id: str, schedule_id: str) -> list[IrScheduleOverride]:
        stmt = select(IrScheduleOverride).where(
            IrScheduleOverride.organization_id == organization_id,
            IrScheduleOverride.schedule_id == schedule_id,
        ).order_by(IrScheduleOverride.starts_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def active_override(self, organization_id: str, schedule_id: str, now: datetime) -> IrScheduleOverride | None:
        stmt = select(IrScheduleOverride).where(
            IrScheduleOverride.organization_id == organization_id,
            IrScheduleOverride.schedule_id == schedule_id,
            IrScheduleOverride.starts_at <= now,
            IrScheduleOverride.ends_at >= now,
        ).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()


class IrStatusPageRepo(BaseRepository[IrStatusPage]):
    def __init__(self, session: AsyncSession):
        super().__init__(IrStatusPage, session)

    async def list_for_org(self, organization_id: str) -> list[IrStatusPage]:
        stmt = select(IrStatusPage).where(
            IrStatusPage.organization_id == organization_id,
            IrStatusPage.is_active.is_(True),
        ).order_by(IrStatusPage.created_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_slug(self, organization_id: str, slug: str) -> IrStatusPage | None:
        stmt = select(IrStatusPage).where(
            IrStatusPage.organization_id == organization_id,
            IrStatusPage.slug == slug,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class IrStatusComponentRepo(BaseRepository[IrStatusComponent]):
    def __init__(self, session: AsyncSession):
        super().__init__(IrStatusComponent, session)

    async def list_for_page(self, organization_id: str, page_id: str) -> list[IrStatusComponent]:
        stmt = select(IrStatusComponent).where(
            IrStatusComponent.organization_id == organization_id,
            IrStatusComponent.page_id == page_id,
        ).order_by(IrStatusComponent.position)
        return list((await self.session.execute(stmt)).scalars().all())


class IrStatusIncidentRepo(BaseRepository[IrStatusIncident]):
    def __init__(self, session: AsyncSession):
        super().__init__(IrStatusIncident, session)

    async def list_for_page(self, organization_id: str, page_id: str, *, limit: int = 50) -> list[IrStatusIncident]:
        stmt = select(IrStatusIncident).where(
            IrStatusIncident.organization_id == organization_id,
            IrStatusIncident.page_id == page_id,
        ).order_by(IrStatusIncident.started_at.desc()).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())


class IrStatusSubscriberRepo(BaseRepository[IrStatusSubscriber]):
    def __init__(self, session: AsyncSession):
        super().__init__(IrStatusSubscriber, session)


class IrCommunicationTemplateRepo(BaseRepository[IrCommunicationTemplate]):
    def __init__(self, session: AsyncSession):
        super().__init__(IrCommunicationTemplate, session)

    async def list_for_org(self, organization_id: str) -> list[IrCommunicationTemplate]:
        stmt = select(IrCommunicationTemplate).where(
            IrCommunicationTemplate.organization_id == organization_id,
        ).order_by(IrCommunicationTemplate.created_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())


class IrCommunicationRepo(BaseRepository[IrCommunication]):
    def __init__(self, session: AsyncSession):
        super().__init__(IrCommunication, session)

    async def list_for_org(self, organization_id: str, *, incident_id: str | None = None) -> list[IrCommunication]:
        filters = [IrCommunication.organization_id == organization_id]
        if incident_id:
            filters.append(IrCommunication.incident_id == incident_id)
        stmt = select(IrCommunication).where(*filters).order_by(IrCommunication.created_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())


class IrMajorIncidentRepo(BaseRepository[IrMajorIncident]):
    def __init__(self, session: AsyncSession):
        super().__init__(IrMajorIncident, session)

    async def list_active(self, organization_id: str) -> list[IrMajorIncident]:
        stmt = select(IrMajorIncident).where(
            IrMajorIncident.organization_id == organization_id,
            IrMajorIncident.status == "ACTIVE",
        ).order_by(IrMajorIncident.started_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_incident(self, organization_id: str, incident_id: str) -> IrMajorIncident | None:
        stmt = select(IrMajorIncident).where(
            IrMajorIncident.organization_id == organization_id,
            IrMajorIncident.incident_id == incident_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class IrCoordinatorRunRepo(BaseRepository[IrCoordinatorRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(IrCoordinatorRun, session)
