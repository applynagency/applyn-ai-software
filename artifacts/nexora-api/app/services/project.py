from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import NotFoundError, ForbiddenError
from app.repositories.project import ProjectRepository
from app.repositories.workspace import WorkspaceRepository
from app.repositories.audit import AuditLogRepository
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse
from app.models.user import User
from app.core.logging import get_logger

logger = get_logger(__name__)


class ProjectService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.project_repo = ProjectRepository(session)
        self.workspace_repo = WorkspaceRepository(session)
        self.audit_repo = AuditLogRepository(session)

    async def create(self, data: ProjectCreate, current_user: User) -> ProjectResponse:
        workspace = await self.workspace_repo.get_by_id(data.workspace_id)
        if not workspace:
            raise NotFoundError("Workspace", data.workspace_id)
        if workspace.owner_id != current_user.id and not current_user.is_superuser:
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
        self, current_user: User, workspace_id: str | None = None, offset: int = 0, limit: int = 50
    ) -> ProjectListResponse:
        if workspace_id:
            items, total = await self.project_repo.list_by_workspace(
                workspace_id, offset=offset, limit=limit
            )
        else:
            items, total = await self.project_repo.list_by_owner(
                current_user.id, offset=offset, limit=limit
            )
        return ProjectListResponse(
            items=[ProjectResponse.model_validate(p) for p in items],
            total=total,
        )

    async def get(self, project_id: str, current_user: User) -> ProjectResponse:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundError("Project", project_id)
        if project.owner_id != current_user.id and not current_user.is_superuser:
            raise ForbiddenError()
        return ProjectResponse.model_validate(project)

    async def update(
        self, project_id: str, data: ProjectUpdate, current_user: User
    ) -> ProjectResponse:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundError("Project", project_id)
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

    async def delete(self, project_id: str, current_user: User) -> None:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundError("Project", project_id)
        if project.owner_id != current_user.id and not current_user.is_superuser:
            raise ForbiddenError()

        await self.project_repo.soft_delete(project)

        await self.audit_repo.log(
            action="project.delete",
            resource_type="project",
            resource_id=project_id,
            user_id=current_user.id,
        )
