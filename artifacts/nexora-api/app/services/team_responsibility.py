from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.team import TeamResponsibilityRepository
from app.schemas.team import (
    TeamResponsibilityCreate,
    TeamResponsibilityResponse,
    TeamResponsibilityUpdate,
)
from app.tenancy.guards import get_team_for_org
from app.tenancy.permissions import can_write_teams

logger = get_logger(__name__)


class TeamResponsibilityService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.responsibility_repo = TeamResponsibilityRepository(session)
        self.audit_repo = AuditLogRepository(session)

    async def create(
        self,
        team_id: str,
        data: TeamResponsibilityCreate,
        current_user: User,
        org_context: OrgContext,
    ) -> TeamResponsibilityResponse:
        await get_team_for_org(self.session, team_id, org_context)
        if not current_user.is_superuser and (
            not org_context.role or not can_write_teams(org_context.role)
        ):
            raise ForbiddenError()

        responsibility = await self.responsibility_repo.create(
            team_id=team_id,
            title=data.title,
            description=data.description,
            priority=data.priority,
        )
        await self.audit_repo.log(
            action="responsibility_created",
            resource_type="team_responsibility",
            resource_id=responsibility.id,
            user_id=current_user.id,
            details={"team_id": team_id},
        )
        return TeamResponsibilityResponse.model_validate(responsibility)

    async def update(
        self,
        responsibility_id: str,
        data: TeamResponsibilityUpdate,
        current_user: User,
        org_context: OrgContext,
    ) -> TeamResponsibilityResponse:
        responsibility = await self.responsibility_repo.get_with_team(responsibility_id)
        if not responsibility:
            raise NotFoundError("TeamResponsibility", responsibility_id)

        await get_team_for_org(self.session, responsibility.team_id, org_context)
        if not current_user.is_superuser and (
            not org_context.role or not can_write_teams(org_context.role)
        ):
            raise ForbiddenError()

        updated = await self.responsibility_repo.update(
            responsibility, **data.model_dump(exclude_none=True)
        )
        await self.audit_repo.log(
            action="responsibility_updated",
            resource_type="team_responsibility",
            resource_id=responsibility_id,
            user_id=current_user.id,
            details={"team_id": responsibility.team_id},
        )
        return TeamResponsibilityResponse.model_validate(updated)

    async def delete(
        self,
        responsibility_id: str,
        current_user: User,
        org_context: OrgContext,
    ) -> None:
        responsibility = await self.responsibility_repo.get_with_team(responsibility_id)
        if not responsibility:
            raise NotFoundError("TeamResponsibility", responsibility_id)

        await get_team_for_org(self.session, responsibility.team_id, org_context)
        if not current_user.is_superuser and (
            not org_context.role or not can_write_teams(org_context.role)
        ):
            raise ForbiddenError()

        team_id = responsibility.team_id
        await self.responsibility_repo.hard_delete(responsibility)
        await self.audit_repo.log(
            action="responsibility_deleted",
            resource_type="team_responsibility",
            resource_id=responsibility_id,
            user_id=current_user.id,
            details={"team_id": team_id},
        )
