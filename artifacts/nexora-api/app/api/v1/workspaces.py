from fastapi import APIRouter, Query
from app.auth.dependencies import CurrentUser, DBSession
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate, WorkspaceResponse, WorkspaceListResponse
from app.services.workspace import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


@router.post("", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(data: WorkspaceCreate, current_user: CurrentUser, session: DBSession):
    service = WorkspaceService(session)
    return await service.create(data, current_user)


@router.get("", response_model=WorkspaceListResponse)
async def list_workspaces(
    current_user: CurrentUser,
    session: DBSession,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    service = WorkspaceService(session)
    return await service.list_for_user(current_user, offset=offset, limit=limit)


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(workspace_id: str, current_user: CurrentUser, session: DBSession):
    service = WorkspaceService(session)
    return await service.get(workspace_id, current_user)


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: str, data: WorkspaceUpdate, current_user: CurrentUser, session: DBSession
):
    service = WorkspaceService(session)
    return await service.update(workspace_id, data, current_user)


@router.delete("/{workspace_id}", status_code=204)
async def delete_workspace(workspace_id: str, current_user: CurrentUser, session: DBSession):
    service = WorkspaceService(session)
    await service.delete(workspace_id, current_user)
