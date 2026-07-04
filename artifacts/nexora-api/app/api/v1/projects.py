
from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.project import ProjectCreate, ProjectListResponse, ProjectResponse, ProjectUpdate
from app.services.project import ProjectService

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    data: ProjectCreate,
    current_user: CurrentUser,
    org_context: OrgContextDep,
    session: DBSession,
):
    service = ProjectService(session)
    return await service.create(data, current_user, org_context)


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    current_user: CurrentUser,
    org_context: OrgContextDep,
    session: DBSession,
    workspace_id: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    service = ProjectService(session)
    return await service.list_for_user(
        current_user, org_context, workspace_id=workspace_id, offset=offset, limit=limit
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: CurrentUser,
    org_context: OrgContextDep,
    session: DBSession,
):
    service = ProjectService(session)
    return await service.get(project_id, current_user, org_context)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    data: ProjectUpdate,
    current_user: CurrentUser,
    org_context: OrgContextDep,
    session: DBSession,
):
    service = ProjectService(session)
    return await service.update(project_id, data, current_user, org_context)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    current_user: CurrentUser,
    org_context: OrgContextDep,
    session: DBSession,
):
    service = ProjectService(session)
    await service.delete(project_id, current_user, org_context)
