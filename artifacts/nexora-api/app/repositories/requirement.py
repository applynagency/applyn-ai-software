from sqlalchemy.ext.asyncio import AsyncSession
from app.models.requirement import Requirement, RequirementStatus
from app.repositories.base import BaseRepository


class RequirementRepository(BaseRepository[Requirement]):
    def __init__(self, session: AsyncSession):
        super().__init__(Requirement, session)

    async def list_by_project(
        self, project_id: str, offset: int = 0, limit: int = 50
    ) -> tuple[list[Requirement], int]:
        return await self.list_all(
            filters=[Requirement.project_id == project_id],
            offset=offset,
            limit=limit,
        )

    async def list_by_status(
        self, status: RequirementStatus, offset: int = 0, limit: int = 50
    ) -> tuple[list[Requirement], int]:
        return await self.list_all(
            filters=[Requirement.status == status],
            offset=offset,
            limit=limit,
        )
