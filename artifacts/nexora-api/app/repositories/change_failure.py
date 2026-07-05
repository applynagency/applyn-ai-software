"""Sprint 44C — data access for change failure predictions."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.change_failure import ChangeFailurePrediction
from app.repositories.base import BaseRepository


class ChangeFailurePredictionRepository(BaseRepository[ChangeFailurePrediction]):
    def __init__(self, session: AsyncSession):
        super().__init__(ChangeFailurePrediction, session)

    async def get_for_org(
        self, prediction_id: str, organization_id: str
    ) -> ChangeFailurePrediction | None:
        stmt = select(ChangeFailurePrediction).where(
            ChangeFailurePrediction.id == prediction_id,
            ChangeFailurePrediction.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_org(
        self, organization_id: str, *, limit: int = 100
    ) -> list[ChangeFailurePrediction]:
        stmt = (
            select(ChangeFailurePrediction)
            .where(ChangeFailurePrediction.organization_id == organization_id)
            .order_by(ChangeFailurePrediction.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())
