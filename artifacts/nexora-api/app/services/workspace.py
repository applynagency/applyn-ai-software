from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import NotFoundError, ConflictError, ForbiddenError
from app.repositories.workspace import WorkspaceRepository
from app.repositories.audit import AuditLogRepository
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate, WorkspaceResponse, WorkspaceListResponse
from app.models.user import User
from app.core.logging import get_logger

logger = get_logger(__name__)


class WorkspaceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.workspace_repo = WorkspaceRepository(session)
        self.audit_repo = AuditLogRepository(session)

    async def create(self, data: WorkspaceCreate, current_user: User) -> WorkspaceResponse:
        existing = await self.workspace_repo.get_by_slug(data.slug, current_user.id)
        if existing:
            raise ConflictError(f"Workspace with slug '{data.slug}' already exists")

        workspace = await self.workspace_repo.create(
            name=data.name,
            description=data.description,
            slug=data.slug,
            owner_id=current_user.id,
        )

        await self.audit_repo.log(
            action="workspace.create",
            resource_type="workspace",
            resource_id=workspace.id,
            user_id=current_user.id,
        )

        logger.info("workspace_created", workspace_id=workspace.id, user_id=current_user.id)
        return WorkspaceResponse.model_validate(workspace)

    async def list_for_user(
        self, current_user: User, offset: int = 0, limit: int = 50
    ) -> WorkspaceListResponse:
        items, total = await self.workspace_repo.list_by_owner(
            current_user.id, offset=offset, limit=limit
        )
        return WorkspaceListResponse(
            items=[WorkspaceResponse.model_validate(w) for w in items],
            total=total,
        )

    async def get(self, workspace_id: str, current_user: User) -> WorkspaceResponse:
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace", workspace_id)
        if workspace.owner_id != current_user.id and not current_user.is_superuser:
            raise ForbiddenError()
        return WorkspaceResponse.model_validate(workspace)

    async def update(
        self, workspace_id: str, data: WorkspaceUpdate, current_user: User
    ) -> WorkspaceResponse:
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace", workspace_id)
        if workspace.owner_id != current_user.id and not current_user.is_superuser:
            raise ForbiddenError()

        update_data = data.model_dump(exclude_none=True)
        updated = await self.workspace_repo.update(workspace, **update_data)

        await self.audit_repo.log(
            action="workspace.update",
            resource_type="workspace",
            resource_id=workspace_id,
            user_id=current_user.id,
            details=update_data,
        )

        return WorkspaceResponse.model_validate(updated)

    async def delete(self, workspace_id: str, current_user: User) -> None:
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace", workspace_id)
        if workspace.owner_id != current_user.id and not current_user.is_superuser:
            raise ForbiddenError()

        await self.workspace_repo.soft_delete(workspace)

        await self.audit_repo.log(
            action="workspace.delete",
            resource_type="workspace",
            resource_id=workspace_id,
            user_id=current_user.id,
        )

        logger.info("workspace_deleted", workspace_id=workspace_id, user_id=current_user.id)
