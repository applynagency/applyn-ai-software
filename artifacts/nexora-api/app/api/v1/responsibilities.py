from fastapi import APIRouter

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.team import TeamResponsibilityResponse, TeamResponsibilityUpdate
from app.services.team_responsibility import TeamResponsibilityService

router = APIRouter(prefix="/responsibilities", tags=["Team Responsibilities"])


@router.put("/{responsibility_id}", response_model=TeamResponsibilityResponse)
async def update_responsibility(
    responsibility_id: str,
    data: TeamResponsibilityUpdate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = TeamResponsibilityService(session)
    return await service.update(responsibility_id, data, current_user, org_context)


@router.delete("/{responsibility_id}", status_code=204)
async def delete_responsibility(
    responsibility_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = TeamResponsibilityService(session)
    await service.delete(responsibility_id, current_user, org_context)
