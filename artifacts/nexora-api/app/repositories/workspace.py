from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.workspace import Workspace
from app.repositories.base import BaseRepository


class WorkspaceRepository(BaseRepository[Workspace]):
    def __init__(self, session: AsyncSession):
        super().__init__(Workspace, session)

    async def get_by_slug(self, slug: str, owner_id: str) -> Optional[Workspace]:
        stmt = select(Workspace).where(
            Workspace.slug == slug,
            Workspace.owner_id == owner_id,
            Workspace.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_owner(
        self, owner_id: str, offset: int = 0, limit: int = 50
    ) -> tuple[list[Workspace], int]:
        return await self.list_all(
            filters=[Workspace.owner_id == owner_id],
            offset=offset,
            limit=limit,
        )
