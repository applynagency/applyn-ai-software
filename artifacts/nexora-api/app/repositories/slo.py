"""Sprint 42C — data access for the service catalog & SLO definitions."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.slo import Service, ServiceSLO
from app.repositories.base import BaseRepository


class ServiceRepository(BaseRepository[Service]):
    def __init__(self, session: AsyncSession):
        super().__init__(Service, session)

    async def get_for_org(self, service_id: str, organization_id: str) -> Service | None:
        stmt = select(Service).where(
            Service.id == service_id, Service.organization_id == organization_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_org(self, organization_id: str) -> list[Service]:
        stmt = (
            select(Service)
            .where(Service.organization_id == organization_id)
            .order_by(Service.name.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def find_by_name(self, organization_id: str, name: str) -> Service | None:
        stmt = (
            select(Service)
            .where(Service.organization_id == organization_id, Service.name == name)
            .order_by(Service.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class ServiceSLORepository(BaseRepository[ServiceSLO]):
    def __init__(self, session: AsyncSession):
        super().__init__(ServiceSLO, session)

    async def get_for_org(self, slo_id: str, organization_id: str) -> ServiceSLO | None:
        stmt = select(ServiceSLO).where(
            ServiceSLO.id == slo_id, ServiceSLO.organization_id == organization_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_service(self, service_id: str, organization_id: str) -> list[ServiceSLO]:
        stmt = (
            select(ServiceSLO)
            .where(
                ServiceSLO.service_id == service_id,
                ServiceSLO.organization_id == organization_id,
            )
            .order_by(ServiceSLO.created_at.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())
