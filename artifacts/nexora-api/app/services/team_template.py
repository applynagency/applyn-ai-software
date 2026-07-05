from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.team import (
    TeamAgentMappingRepository,
    TeamRepository,
    TeamResponsibilityRepository,
)
from app.schemas.team import (
    TeamResponse,
    TeamTemplateApplyRequest,
    TeamTemplateApplyResponse,
    TeamTemplateListResponse,
    TeamTemplateResponse,
    TeamTemplateTeamPreview,
)
from app.services.team import TeamService
from app.teams.mappings import TeamMappingService
from app.teams.templates import (
    TEAM_TEMPLATES,
    get_template_by_slug,
    get_template_definition,
)
from app.tenancy.permissions import can_read_teams, can_write_teams

logger = get_logger(__name__)


class TeamTemplateService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.team_repo = TeamRepository(session)
        self.responsibility_repo = TeamResponsibilityRepository(session)
        self.mapping_repo = TeamAgentMappingRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.mapping_service = TeamMappingService()
        self.team_service = TeamService(session)

    async def list_templates(
        self, current_user: User, org_context: OrgContext, *, include_definition: bool = False
    ) -> TeamTemplateListResponse:
        if not current_user.is_superuser and (
            not org_context.role or not can_read_teams(org_context.role)
        ):
            raise ForbiddenError()

        items = []
        for template in TEAM_TEMPLATES:
            items.append(
                TeamTemplateResponse(
                    slug=template.slug,
                    name=template.name,
                    description=template.description,
                    industry=template.industry,
                    team_count=len(template.teams),
                    teams=[
                        TeamTemplateTeamPreview(
                            name=team.name,
                            description=team.description,
                            team_type=team.team_type,
                            responsibility_count=len(team.responsibilities or []),
                        )
                        for team in template.teams
                    ],
                    definition=get_template_definition(template.slug) if include_definition else None,
                )
            )
        return TeamTemplateListResponse(items=items, total=len(items))

    async def get_template(
        self, slug: str, current_user: User, org_context: OrgContext
    ) -> TeamTemplateResponse:
        if not current_user.is_superuser and (
            not org_context.role or not can_read_teams(org_context.role)
        ):
            raise ForbiddenError()

        template = get_template_by_slug(slug)
        if not template:
            raise NotFoundError("TeamTemplate", slug)

        return TeamTemplateResponse(
            slug=template.slug,
            name=template.name,
            description=template.description,
            industry=template.industry,
            team_count=len(template.teams),
            teams=[
                TeamTemplateTeamPreview(
                    name=team.name,
                    description=team.description,
                    team_type=team.team_type,
                    responsibility_count=len(team.responsibilities or []),
                )
                for team in template.teams
            ],
            definition=get_template_definition(slug),
        )

    async def apply_template(
        self,
        data: TeamTemplateApplyRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> TeamTemplateApplyResponse:
        organization_id = org_context.requires_organization
        if not current_user.is_superuser and (
            not org_context.role or not can_write_teams(org_context.role)
        ):
            raise ForbiddenError()

        template = get_template_by_slug(data.template_slug)
        if not template:
            raise NotFoundError("TeamTemplate", data.template_slug)

        created_teams: list[TeamResponse] = []
        created_team_ids: list[str] = []
        for template_team in template.teams:
            team = await self.team_repo.create(
                organization_id=organization_id,
                name=template_team.name,
                description=template_team.description,
                team_type=template_team.team_type,
                status=template_team.status,
                created_by=current_user.id,
            )
            created_team_ids.append(team.id)

            for responsibility in template_team.responsibilities or []:
                await self.responsibility_repo.create(
                    team_id=team.id,
                    title=responsibility.title,
                    description=responsibility.description,
                    priority=responsibility.priority,
                )

            specs = self.mapping_service.mapping_specs_for_team_type(template_team.team_type)
            if specs:
                await self.mapping_repo.replace_for_team(team.id, specs)

            loaded = await self.team_repo.get_with_details(team.id)
            if loaded:
                created_teams.append(await self.team_service._to_response(loaded))

        await self.audit_repo.log(
            action="template_applied",
            resource_type="team_template",
            resource_id=data.template_slug,
            user_id=current_user.id,
            details={
                "template_slug": data.template_slug,
                "teams_created": len(created_teams),
                "team_ids": created_team_ids,
            },
        )
        logger.info(
            "team_template_applied",
            template_slug=data.template_slug,
            organization_id=organization_id,
            teams_created=len(created_teams),
        )
        return TeamTemplateApplyResponse(
            template_slug=data.template_slug,
            teams_created=len(created_teams),
            items=created_teams,
        )
