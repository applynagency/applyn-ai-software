from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError
from app.core.logging import get_logger
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.project import ProjectRepository
from app.repositories.workspace import WorkspaceRepository
from app.schemas.project import ProjectCreate, ProjectListResponse, ProjectResponse, ProjectUpdate
from app.tenancy.guards import ensure_workspace_write, get_project_for_org, get_workspace_for_org
from app.tenancy.permissions import can_write_resources

logger = get_logger(__name__)


class ProjectService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.project_repo = ProjectRepository(session)
        self.workspace_repo = WorkspaceRepository(session)
        self.audit_repo = AuditLogRepository(session)

    async def create(
        self, data: ProjectCreate, current_user: User, org_context: OrgContext
    ) -> ProjectResponse:
        workspace = await get_workspace_for_org(self.session, data.workspace_id, org_context)
        await ensure_workspace_write(self.session, workspace, org_context)
        if workspace.owner_id != current_user.id and not current_user.is_superuser:
            if not org_context.role or not can_write_resources(org_context.role):
                raise ForbiddenError("You don't have access to this workspace")

        project = await self.project_repo.create(
            name=data.name,
            description=data.description,
            workspace_id=data.workspace_id,
            owner_id=current_user.id,
        )

        await self.audit_repo.log(
            action="project.create",
            resource_type="project",
            resource_id=project.id,
            user_id=current_user.id,
        )

        logger.info("project_created", project_id=project.id, user_id=current_user.id)
        return ProjectResponse.model_validate(project)

    async def list_for_user(
        self,
        current_user: User,
        org_context: OrgContext,
        workspace_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> ProjectListResponse:
        organization_id = org_context.requires_organization
        if workspace_id:
            await get_workspace_for_org(self.session, workspace_id, org_context)
            items, total = await self.project_repo.list_by_workspace(
                workspace_id, offset=offset, limit=limit
            )
        else:
            items, total = await self.project_repo.list_by_organization(
                organization_id, offset=offset, limit=limit
            )
        return ProjectListResponse(
            items=[ProjectResponse.model_validate(p) for p in items],
            total=total,
        )

    async def get(
        self, project_id: str, current_user: User, org_context: OrgContext
    ) -> ProjectResponse:
        project = await get_project_for_org(self.session, project_id, org_context)
        if project.owner_id != current_user.id and not current_user.is_superuser:
            if not org_context.role or not can_write_resources(org_context.role):
                raise ForbiddenError()
        return ProjectResponse.model_validate(project)

    async def update(
        self, project_id: str, data: ProjectUpdate, current_user: User, org_context: OrgContext
    ) -> ProjectResponse:
        project = await get_project_for_org(self.session, project_id, org_context)
        if project.owner_id != current_user.id and not current_user.is_superuser:
            raise ForbiddenError()

        update_data = data.model_dump(exclude_none=True)
        updated = await self.project_repo.update(project, **update_data)

        await self.audit_repo.log(
            action="project.update",
            resource_type="project",
            resource_id=project_id,
            user_id=current_user.id,
            details=update_data,
        )

        return ProjectResponse.model_validate(updated)

    async def delete(
        self, project_id: str, current_user: User, org_context: OrgContext
    ) -> None:
        project = await get_project_for_org(self.session, project_id, org_context)
        if project.owner_id != current_user.id and not current_user.is_superuser:
            raise ForbiddenError()

        await self.project_repo.soft_delete(project)

        await self.audit_repo.log(
            action="project.delete",
            resource_type="project",
            resource_id=project_id,
            user_id=current_user.id,
        )
