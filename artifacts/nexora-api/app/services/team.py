from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.team import Team, TeamStatus
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.team import (
    TeamAgentMappingRepository,
    TeamRepository,
    TeamResponsibilityRepository,
)
from app.repositories.workflow import WorkflowStageTeamRepository
from app.schemas.team import (
    TeamAuditEventResponse,
    TeamAuditListResponse,
    TeamCreate,
    TeamDuplicateResponse,
    TeamListResponse,
    TeamResponse,
    TeamUpdate,
)
from app.teams.mappings import AgentMappingSpec, TeamMappingService
from app.tenancy.guards import get_team_for_org
from app.tenancy.permissions import can_manage_teams, can_read_teams, can_write_teams

logger = get_logger(__name__)


class TeamService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.team_repo = TeamRepository(session)
        self.responsibility_repo = TeamResponsibilityRepository(session)
        self.mapping_repo = TeamAgentMappingRepository(session)
        self.stage_team_repo = WorkflowStageTeamRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.mapping_service = TeamMappingService()

    async def _to_response(self, team: Team) -> TeamResponse:
        response = TeamResponse.model_validate(team)
        response.responsibility_count = len(team.responsibilities or [])
        response.agent_count = len(team.agent_mappings or [])
        response.workflow_count = await self.stage_team_repo.count_for_team(team.id)
        response.agent_mappings = sorted(
            response.agent_mappings,
            key=lambda mapping: mapping.execution_order,
        )
        return response

    async def _seed_agent_mappings(self, team: Team) -> None:
        specs = self.mapping_service.mapping_specs_for_team_type(team.team_type)
        if specs:
            await self.mapping_repo.replace_for_team(team.id, specs)

    def _ensure_read(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_read_teams(org_context.role)
        ):
            raise ForbiddenError()

    def _ensure_write(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_write_teams(org_context.role)
        ):
            raise ForbiddenError()

    def _ensure_manage(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_manage_teams(org_context.role)
        ):
            raise ForbiddenError()

    async def create(
        self, data: TeamCreate, current_user: User, org_context: OrgContext
    ) -> TeamResponse:
        organization_id = org_context.requires_organization
        self._ensure_write(current_user, org_context)

        team = await self.team_repo.create(
            organization_id=organization_id,
            name=data.name,
            description=data.description,
            team_type=data.team_type,
            status=data.status,
            created_by=current_user.id,
        )
        await self._seed_agent_mappings(team)
        team = await self.team_repo.get_with_details(team.id)

        await self.audit_repo.log(
            action="team_created",
            resource_type="team",
            resource_id=team.id,
            user_id=current_user.id,
            details={"team_type": data.team_type.value, "team_id": team.id},
        )
        logger.info("team_created", team_id=team.id, organization_id=organization_id)
        return await self._to_response(team)

    async def list_for_organization(
        self,
        current_user: User,
        org_context: OrgContext,
        *,
        team_type=None,
        status=None,
        offset: int = 0,
        limit: int = 50,
    ) -> TeamListResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)

        items, total = await self.team_repo.list_by_organization(
            organization_id,
            team_type=team_type,
            status=status,
            offset=offset,
            limit=limit,
        )
        detailed = []
        for item in items:
            team = await self.team_repo.get_with_details(item.id)
            if team:
                detailed.append(await self._to_response(team))
        return TeamListResponse(items=detailed, total=total)

    async def get(
        self, team_id: str, current_user: User, org_context: OrgContext
    ) -> TeamResponse:
        team = await get_team_for_org(self.session, team_id, org_context)
        self._ensure_read(current_user, org_context)
        return await self._to_response(team)

    async def update(
        self, team_id: str, data: TeamUpdate, current_user: User, org_context: OrgContext
    ) -> TeamResponse:
        team = await get_team_for_org(self.session, team_id, org_context)
        self._ensure_write(current_user, org_context)

        update_data = data.model_dump(exclude_none=True)
        previous_type = team.team_type
        updated = await self.team_repo.update(team, **update_data)

        if data.team_type and data.team_type != previous_type:
            await self._seed_agent_mappings(updated)

        team = await self.team_repo.get_with_details(updated.id)
        await self.audit_repo.log(
            action="team_updated",
            resource_type="team",
            resource_id=team_id,
            user_id=current_user.id,
            details={"team_id": team_id, **update_data},
        )
        return await self._to_response(team)

    async def archive(
        self, team_id: str, current_user: User, org_context: OrgContext
    ) -> TeamResponse:
        team = await get_team_for_org(self.session, team_id, org_context)
        self._ensure_manage(current_user, org_context)

        updated = await self.team_repo.update(team, status=TeamStatus.ARCHIVED)
        team = await self.team_repo.get_with_details(updated.id)
        await self.audit_repo.log(
            action="team_archived",
            resource_type="team",
            resource_id=team_id,
            user_id=current_user.id,
            details={"team_id": team_id},
        )
        return await self._to_response(team)

    async def delete(
        self, team_id: str, current_user: User, org_context: OrgContext
    ) -> None:
        team = await get_team_for_org(self.session, team_id, org_context)
        self._ensure_manage(current_user, org_context)

        await self.team_repo.hard_delete(team)
        await self.audit_repo.log(
            action="team_deleted",
            resource_type="team",
            resource_id=team_id,
            user_id=current_user.id,
            details={"team_id": team_id},
        )
        logger.info("team_deleted", team_id=team_id)

    async def duplicate(
        self, team_id: str, current_user: User, org_context: OrgContext
    ) -> TeamDuplicateResponse:
        source = await get_team_for_org(self.session, team_id, org_context)
        source = await self.team_repo.get_with_details(source.id)
        if not source:
            raise NotFoundError("Team", team_id)
        self._ensure_write(current_user, org_context)

        duplicate_team = await self.team_repo.create(
            organization_id=source.organization_id,
            name=f"{source.name} (Copy)",
            description=source.description,
            team_type=source.team_type,
            status=TeamStatus.DRAFT,
            created_by=current_user.id,
        )

        for responsibility in await self.responsibility_repo.list_for_team(source.id):
            await self.responsibility_repo.create(
                team_id=duplicate_team.id,
                title=responsibility.title,
                description=responsibility.description,
                priority=responsibility.priority,
            )

        if source.agent_mappings:
            specs = [
                AgentMappingSpec(
                    internal_agent=mapping.internal_agent,
                    execution_order=mapping.execution_order,
                    is_required=mapping.is_required,
                )
                for mapping in sorted(source.agent_mappings, key=lambda item: item.execution_order)
            ]
            await self.mapping_repo.replace_for_team(duplicate_team.id, specs)
        else:
            await self._seed_agent_mappings(duplicate_team)

        team = await self.team_repo.get_with_details(duplicate_team.id)
        await self.audit_repo.log(
            action="team_duplicated",
            resource_type="team",
            resource_id=duplicate_team.id,
            user_id=current_user.id,
            details={"team_id": duplicate_team.id, "source_team_id": team_id},
        )
        return TeamDuplicateResponse(team=await self._to_response(team))

    async def list_audit_events(
        self, team_id: str, current_user: User, org_context: OrgContext, *, offset: int = 0, limit: int = 50
    ) -> TeamAuditListResponse:
        await get_team_for_org(self.session, team_id, org_context)
        self._ensure_read(current_user, org_context)
        items, total = await self.audit_repo.list_for_team(team_id, offset=offset, limit=limit)
        return TeamAuditListResponse(
            items=[TeamAuditEventResponse.model_validate(item) for item in items],
            total=total,
        )
