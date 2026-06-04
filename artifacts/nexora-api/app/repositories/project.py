from sqlalchemy.ext.asyncio import AsyncSession
from app.models.project import Project
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
