from fastapi import APIRouter, Query
from app.auth.dependencies import CurrentUser, DBSession
from app.schemas.requirement import RequirementCreate, RequirementUpdate, RequirementResponse, RequirementListResponse
from app.services.requirement import RequirementService

router = APIRouter(prefix="/requirements", tags=["Requirements"])


@router.post("", response_model=RequirementResponse, status_code=201)
async def submit_requirement(data: RequirementCreate, current_user: CurrentUser, session: DBSession):
    service = RequirementService(session)
    return await service.submit(data, current_user)


@router.get("", response_model=RequirementListResponse)
async def list_requirements(
    current_user: CurrentUser,
    session: DBSession,
    project_id: str = Query(..., description="Filter by project ID"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    service = RequirementService(session)
    return await service.list_for_project(project_id, current_user, offset=offset, limit=limit)


@router.get("/{requirement_id}", response_model=RequirementResponse)
async def get_requirement(requirement_id: str, current_user: CurrentUser, session: DBSession):
    service = RequirementService(session)
    return await service.get(requirement_id, current_user)


@router.patch("/{requirement_id}", response_model=RequirementResponse)
async def update_requirement(
    requirement_id: str, data: RequirementUpdate, current_user: CurrentUser, session: DBSession
):
    service = RequirementService(session)
    return await service.update(requirement_id, data, current_user)
