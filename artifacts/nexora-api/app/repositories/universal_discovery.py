"""Sprint 58A.2.1 — data access for the Universal Discovery Framework."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.universal_discovery import (
    DiscoveredAsset,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    UniversalDiscoveryEvent,
)
from app.repositories.base import BaseRepository


class DiscoveredAssetRepository(BaseRepository[DiscoveredAsset]):
    def __init__(self, session: AsyncSession):
        super().__init__(DiscoveredAsset, session)

    async def list_for_org(self, organization_id: str) -> list[DiscoveredAsset]:
        stmt = select(DiscoveredAsset).where(
            DiscoveredAsset.organization_id == organization_id
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def query(
        self, organization_id: str, *, domain: str | None = None,
        provider: str | None = None, limit: int = 500,
    ) -> list[DiscoveredAsset]:
        stmt = select(DiscoveredAsset).where(DiscoveredAsset.organization_id == organization_id)
        if domain:
            stmt = stmt.where(DiscoveredAsset.domain == domain)
        if provider:
            stmt = stmt.where(DiscoveredAsset.provider == provider)
        stmt = stmt.order_by(DiscoveredAsset.last_seen_at.desc().nullslast()).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())


class KnowledgeGraphRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.nodes = BaseRepository(KnowledgeGraphNode, session)
        self.edges = BaseRepository(KnowledgeGraphEdge, session)

    async def list_nodes(self, organization_id: str) -> list[KnowledgeGraphNode]:
        stmt = select(KnowledgeGraphNode).where(
            KnowledgeGraphNode.organization_id == organization_id
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_edges(self, organization_id: str) -> list[KnowledgeGraphEdge]:
        stmt = select(KnowledgeGraphEdge).where(
            KnowledgeGraphEdge.organization_id == organization_id
        )
        return list((await self.session.execute(stmt)).scalars().all())


class UniversalDiscoveryEventRepository(BaseRepository[UniversalDiscoveryEvent]):
    def __init__(self, session: AsyncSession):
        super().__init__(UniversalDiscoveryEvent, session)

    async def list_for_org(
        self, organization_id: str, *, limit: int = 100
    ) -> list[UniversalDiscoveryEvent]:
        stmt = (
            select(UniversalDiscoveryEvent)
            .where(UniversalDiscoveryEvent.organization_id == organization_id)
            .order_by(UniversalDiscoveryEvent.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_for_scan(
        self, scan_run_id: str, organization_id: str
    ) -> list[UniversalDiscoveryEvent]:
        stmt = (
            select(UniversalDiscoveryEvent)
            .where(
                UniversalDiscoveryEvent.scan_run_id == scan_run_id,
                UniversalDiscoveryEvent.organization_id == organization_id,
            )
            .order_by(UniversalDiscoveryEvent.created_at.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())
