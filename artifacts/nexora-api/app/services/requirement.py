from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError
from app.core.logging import get_logger
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.project import ProjectRepository
from app.repositories.requirement import RequirementRepository
from app.schemas.requirement import (
    RequirementCreate,
    RequirementListResponse,
    RequirementResponse,
    RequirementUpdate,
)
from app.tenancy.guards import get_project_for_org, get_requirement_for_org
from app.tenancy.permissions import can_write_resources

logger = get_logger(__name__)


class RequirementService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.req_repo = RequirementRepository(session)
        self.project_repo = ProjectRepository(session)
        self.audit_repo = AuditLogRepository(session)

    async def submit(
        self, data: RequirementCreate, current_user: User, org_context: OrgContext
    ) -> RequirementResponse:
        project = await get_project_for_org(self.session, data.project_id, org_context)
        if project.owner_id != current_user.id and not current_user.is_superuser:
            if not org_context.role or not can_write_resources(org_context.role):
                raise ForbiddenError("You don't have access to this project")

        requirement = await self.req_repo.create(
            title=data.title,
            content=data.content,
            project_id=data.project_id,
            submitted_by=current_user.id,
        )

        await self.audit_repo.log(
            action="requirement.submit",
            resource_type="requirement",
            resource_id=requirement.id,
            user_id=current_user.id,
        )

        logger.info("requirement_submitted", requirement_id=requirement.id, user_id=current_user.id)
        return RequirementResponse.model_validate(requirement)

    async def list_for_project(
        self,
        project_id: str,
        current_user: User,
        org_context: OrgContext,
        offset: int = 0,
        limit: int = 50,
    ) -> RequirementListResponse:
        project = await get_project_for_org(self.session, project_id, org_context)
        if project.owner_id != current_user.id and not current_user.is_superuser:
            if not org_context.role or not can_write_resources(org_context.role):
                raise ForbiddenError()

        items, total = await self.req_repo.list_by_project(project_id, offset=offset, limit=limit)
        return RequirementListResponse(
            items=[RequirementResponse.model_validate(r) for r in items],
            total=total,
        )

    async def get(
        self, requirement_id: str, current_user: User, org_context: OrgContext
    ) -> RequirementResponse:
        req = await get_requirement_for_org(self.session, requirement_id, org_context)
        if req.submitted_by != current_user.id and not current_user.is_superuser:
            if not org_context.role or not can_write_resources(org_context.role):
                raise ForbiddenError()
        return RequirementResponse.model_validate(req)

    async def update(
        self, requirement_id: str, data: RequirementUpdate, current_user: User, org_context: OrgContext
    ) -> RequirementResponse:
        req = await get_requirement_for_org(self.session, requirement_id, org_context)
        if req.submitted_by != current_user.id and not current_user.is_superuser:
            raise ForbiddenError()

        update_data = data.model_dump(exclude_none=True)
        updated = await self.req_repo.update(req, **update_data)
        return RequirementResponse.model_validate(updated)
