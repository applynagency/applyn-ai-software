
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.team import Team, TeamAgentMapping, TeamResponsibility, TeamStatus, TeamType
from app.repositories.base import BaseRepository
from app.teams.mappings import AgentMappingSpec


class TeamRepository(BaseRepository[Team]):
    def __init__(self, session: AsyncSession):
        super().__init__(Team, session)

    async def get_with_details(self, team_id: str) -> Team | None:
        stmt = (
            select(Team)
            .where(Team.id == team_id)
            .options(
                selectinload(Team.responsibilities),
                selectinload(Team.agent_mappings),
            )
            .execution_options(populate_existing=True)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_organization(
        self,
        organization_id: str,
        *,
        team_type: TeamType | None = None,
        status: TeamStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Team], int]:
        filters = [Team.organization_id == organization_id]
        if team_type:
            filters.append(Team.team_type == team_type)
        if status:
            filters.append(Team.status == status)
        return await self.list_all(filters=filters, offset=offset, limit=limit)


class TeamResponsibilityRepository(BaseRepository[TeamResponsibility]):
    def __init__(self, session: AsyncSession):
        super().__init__(TeamResponsibility, session)

    async def get_with_team(self, responsibility_id: str) -> TeamResponsibility | None:
        stmt = (
            select(TeamResponsibility)
            .where(TeamResponsibility.id == responsibility_id)
            .options(selectinload(TeamResponsibility.team))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_team(self, team_id: str) -> list[TeamResponsibility]:
        items, _ = await self.list_all(
            filters=[TeamResponsibility.team_id == team_id],
            limit=500,
        )
        return items


class TeamAgentMappingRepository(BaseRepository[TeamAgentMapping]):
    def __init__(self, session: AsyncSession):
        super().__init__(TeamAgentMapping, session)

    async def list_for_team(self, team_id: str) -> list[TeamAgentMapping]:
        stmt = (
            select(TeamAgentMapping)
            .where(TeamAgentMapping.team_id == team_id)
            .order_by(TeamAgentMapping.execution_order.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def replace_for_team(
        self, team_id: str, mappings: list[AgentMappingSpec]
    ) -> list[TeamAgentMapping]:
        existing, _ = await self.list_all(filters=[TeamAgentMapping.team_id == team_id], limit=100)
        for mapping in existing:
            await self.hard_delete(mapping)

        created = []
        for spec in mappings:
            mapping = await self.create(
                team_id=team_id,
                internal_agent=spec.internal_agent,
                execution_order=spec.execution_order,
                is_required=spec.is_required,
            )
            created.append(mapping)
        return created
