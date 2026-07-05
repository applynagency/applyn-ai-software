"""Sprint 46B - data access for Architecture Discovery."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.architecture import ArchitectureEdge, ArchitectureNode, ArchitectureSnapshot
from app.repositories.base import BaseRepository


class ArchitectureSnapshotRepository(BaseRepository[ArchitectureSnapshot]):
    def __init__(self, session: AsyncSession):
        super().__init__(ArchitectureSnapshot, session)

    async def get_for_org(self, snapshot_id: str, organization_id: str) -> ArchitectureSnapshot | None:
        stmt = select(ArchitectureSnapshot).where(
            ArchitectureSnapshot.id == snapshot_id,
            ArchitectureSnapshot.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_org(self, organization_id: str, *, limit: int = 100) -> list[ArchitectureSnapshot]:
        stmt = (
            select(ArchitectureSnapshot)
            .where(ArchitectureSnapshot.organization_id == organization_id)
            .order_by(ArchitectureSnapshot.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def latest(self, organization_id: str) -> ArchitectureSnapshot | None:
        stmt = (
            select(ArchitectureSnapshot)
            .where(ArchitectureSnapshot.organization_id == organization_id)
            .order_by(ArchitectureSnapshot.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class ArchitectureNodeRepository(BaseRepository[ArchitectureNode]):
    def __init__(self, session: AsyncSession):
        super().__init__(ArchitectureNode, session)

    async def list_for_snapshot(self, snapshot_id: str, organization_id: str) -> list[ArchitectureNode]:
        stmt = (
            select(ArchitectureNode)
            .where(
                ArchitectureNode.snapshot_id == snapshot_id,
                ArchitectureNode.organization_id == organization_id,
            )
            .order_by(ArchitectureNode.node_type.asc(), ArchitectureNode.name.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())


class ArchitectureEdgeRepository(BaseRepository[ArchitectureEdge]):
    def __init__(self, session: AsyncSession):
        super().__init__(ArchitectureEdge, session)

    async def list_for_snapshot(self, snapshot_id: str, organization_id: str) -> list[ArchitectureEdge]:
        stmt = (
            select(ArchitectureEdge)
            .where(
                ArchitectureEdge.snapshot_id == snapshot_id,
                ArchitectureEdge.organization_id == organization_id,
            )
        )
        return list((await self.session.execute(stmt)).scalars().all())
