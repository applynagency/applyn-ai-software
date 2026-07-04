from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.workspace import Workspace
from app.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    def __init__(self, session: AsyncSession):
        super().__init__(Project, session)

    async def list_by_workspace(
        self, workspace_id: str, offset: int = 0, limit: int = 50
    ) -> tuple[list[Project], int]:
        return await self.list_all(
            filters=[Project.workspace_id == workspace_id],
            offset=offset,
            limit=limit,
        )

    async def list_by_owner(
        self, owner_id: str, offset: int = 0, limit: int = 50
    ) -> tuple[list[Project], int]:
        return await self.list_all(
            filters=[Project.owner_id == owner_id],
            offset=offset,
            limit=limit,
        )

    async def list_by_organization(
        self, organization_id: str, offset: int = 0, limit: int = 50
    ) -> tuple[list[Project], int]:
        stmt = (
            select(Project)
            .join(Workspace, Project.workspace_id == Workspace.id)
            .where(
                Workspace.organization_id == organization_id,
                Project.deleted_at.is_(None),
                Workspace.deleted_at.is_(None),
            )
            .offset(offset)
            .limit(limit)
        )
        count_stmt = (
            select(Project)
            .join(Workspace, Project.workspace_id == Workspace.id)
            .where(
                Workspace.organization_id == organization_id,
                Project.deleted_at.is_(None),
                Workspace.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total
