from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.agent import AgentRun, AgentOutput, AgentType, AgentRunStatus
from app.repositories.base import BaseRepository


class AgentRunRepository(BaseRepository[AgentRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(AgentRun, session)

    async def get_with_outputs(self, run_id: str) -> Optional[AgentRun]:
        stmt = (
            select(AgentRun)
            .where(AgentRun.id == run_id)
            .options(selectinload(AgentRun.outputs))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_requirement(
        self, requirement_id: str, offset: int = 0, limit: int = 50
    ) -> tuple[list[AgentRun], int]:
        return await self.list_all(
            filters=[AgentRun.requirement_id == requirement_id],
            offset=offset,
            limit=limit,
        )

    async def get_latest_for_requirement(
        self, requirement_id: str, agent_type: AgentType = AgentType.PRODUCT_OWNER
    ) -> Optional[AgentRun]:
        stmt = (
            select(AgentRun)
            .where(
                AgentRun.requirement_id == requirement_id,
                AgentRun.agent_type == agent_type,
                AgentRun.status == AgentRunStatus.COMPLETED,
            )
            .order_by(AgentRun.created_at.desc())
            .limit(1)
            .options(selectinload(AgentRun.outputs))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class AgentOutputRepository(BaseRepository[AgentOutput]):
    def __init__(self, session: AsyncSession):
        super().__init__(AgentOutput, session)

    async def get_by_run(self, run_id: str) -> list[AgentOutput]:
        stmt = select(AgentOutput).where(AgentOutput.agent_run_id == run_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
