from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.org_config import OrgConfigVariable


class OrgConfigRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_org(self, organization_id: str, environment: str | None = None) -> list[OrgConfigVariable]:
        q = select(OrgConfigVariable).where(OrgConfigVariable.organization_id == organization_id)
        if environment:
            q = q.where(OrgConfigVariable.environment == environment)
        q = q.order_by(OrgConfigVariable.key.asc())
        return list((await self.session.scalars(q)).all())

    async def get_for_org(self, variable_id: str, organization_id: str) -> OrgConfigVariable | None:
        q = select(OrgConfigVariable).where(
            OrgConfigVariable.id == variable_id,
            OrgConfigVariable.organization_id == organization_id,
        )
        return await self.session.scalar(q)

    async def get_by_key(self, organization_id: str, key: str, environment: str) -> OrgConfigVariable | None:
        q = select(OrgConfigVariable).where(
            OrgConfigVariable.organization_id == organization_id,
            OrgConfigVariable.key == key,
            OrgConfigVariable.environment == environment,
        )
        return await self.session.scalar(q)

    async def create(self, **kwargs) -> OrgConfigVariable:
        row = OrgConfigVariable(**kwargs)
        self.session.add(row)
        await self.session.flush()
        return row

    async def update(self, row: OrgConfigVariable, **kwargs) -> OrgConfigVariable:
        for k, v in kwargs.items():
            setattr(row, k, v)
        await self.session.flush()
        return row

    async def delete(self, row: OrgConfigVariable) -> None:
        await self.session.delete(row)
        await self.session.flush()
