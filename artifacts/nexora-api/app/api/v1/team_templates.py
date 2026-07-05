from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.team import (
    TeamTemplateApplyRequest,
    TeamTemplateApplyResponse,
    TeamTemplateListResponse,
    TeamTemplateResponse,
)
from app.services.team_template import TeamTemplateService

router = APIRouter(prefix="/team-templates", tags=["Team Templates"])


@router.get("", response_model=TeamTemplateListResponse)
async def list_team_templates(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    include_definition: bool = Query(default=False),
):
    service = TeamTemplateService(session)
    return await service.list_templates(
        current_user, org_context, include_definition=include_definition
    )


@router.post("/apply", response_model=TeamTemplateApplyResponse, status_code=201)
async def apply_team_template(
    data: TeamTemplateApplyRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = TeamTemplateService(session)
    return await service.apply_template(data, current_user, org_context)


@router.get("/{slug}", response_model=TeamTemplateResponse)
async def get_team_template(
    slug: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = TeamTemplateService(session)
    return await service.get_template(slug, current_user, org_context)
