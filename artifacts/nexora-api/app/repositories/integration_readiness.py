"""Integration readiness persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration_readiness import (
    IntConnectionRegistry,
    IntExpiryReminder,
    IntHealthHistory,
    IntLiveEvidence,
)
from app.repositories.base import BaseRepository


class IntRegistryRepo(BaseRepository[IntConnectionRegistry]):
    def __init__(self, session: AsyncSession):
        super().__init__(IntConnectionRegistry, session)

    async def list_for_org(
        self, organization_id: str, *, state: str | None = None, limit: int = 200,
    ) -> list[IntConnectionRegistry]:
        filters = [IntConnectionRegistry.organization_id == organization_id]
        if state:
            filters.append(IntConnectionRegistry.lifecycle_state == state.upper())
        stmt = select(IntConnectionRegistry).where(*filters).order_by(
            IntConnectionRegistry.updated_at.desc(),
        ).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_resource(
        self, organization_id: str, resource_type: str, resource_id: str,
    ) -> IntConnectionRegistry | None:
        stmt = select(IntConnectionRegistry).where(
            IntConnectionRegistry.organization_id == organization_id,
            IntConnectionRegistry.resource_type == resource_type,
            IntConnectionRegistry.resource_id == resource_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_idempotency(self, organization_id: str, key: str) -> IntConnectionRegistry | None:
        stmt = select(IntConnectionRegistry).where(
            IntConnectionRegistry.organization_id == organization_id,
            IntConnectionRegistry.idempotency_key == key,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class IntHealthHistoryRepo(BaseRepository[IntHealthHistory]):
    def __init__(self, session: AsyncSession):
        super().__init__(IntHealthHistory, session)

    async def list_for_registry(self, registry_id: str, *, limit: int = 50) -> list[IntHealthHistory]:
        stmt = select(IntHealthHistory).where(
            IntHealthHistory.registry_id == registry_id,
        ).order_by(IntHealthHistory.created_at.desc()).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())


class IntExpiryRepo(BaseRepository[IntExpiryReminder]):
    def __init__(self, session: AsyncSession):
        super().__init__(IntExpiryReminder, session)

    async def list_for_registry(self, registry_id: str) -> list[IntExpiryReminder]:
        stmt = select(IntExpiryReminder).where(IntExpiryReminder.registry_id == registry_id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_pending_for_org(self, organization_id: str) -> list[IntExpiryReminder]:
        stmt = select(IntExpiryReminder).where(
            IntExpiryReminder.organization_id == organization_id,
            IntExpiryReminder.acknowledged.is_(False),
        )
        return list((await self.session.execute(stmt)).scalars().all())


class IntLiveEvidenceRepo(BaseRepository[IntLiveEvidence]):
    def __init__(self, session: AsyncSession):
        super().__init__(IntLiveEvidence, session)

    async def list_for_operation(self, operation_id: str) -> list[IntLiveEvidence]:
        stmt = select(IntLiveEvidence).where(IntLiveEvidence.operation_id == operation_id)
        return list((await self.session.execute(stmt)).scalars().all())
