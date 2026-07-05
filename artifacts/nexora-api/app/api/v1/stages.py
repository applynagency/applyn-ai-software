from fastapi import APIRouter

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.workflow import (
    WorkflowStageResponse,
    WorkflowStageTeamAssign,
    WorkflowStageTeamResponse,
    WorkflowStageUpdate,
)
from app.services.workflow_stage import WorkflowStageService

router = APIRouter(prefix="/stages", tags=["Workflow Stages"])


@router.put("/{stage_id}", response_model=WorkflowStageResponse)
async def update_stage(
    stage_id: str,
    data: WorkflowStageUpdate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = WorkflowStageService(session)
    return await service.update(stage_id, data, current_user, org_context)


@router.delete("/{stage_id}", status_code=204)
async def delete_stage(
    stage_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = WorkflowStageService(session)
    await service.delete(stage_id, current_user, org_context)


@router.post("/{stage_id}/teams", response_model=WorkflowStageTeamResponse, status_code=201)
async def assign_team(
    stage_id: str,
    data: WorkflowStageTeamAssign,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = WorkflowStageService(session)
    return await service.assign_team(stage_id, data, current_user, org_context)


@router.delete("/{stage_id}/teams/{team_id}", status_code=204)
async def unassign_team(
    stage_id: str,
    team_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = WorkflowStageService(session)
    await service.unassign_team(stage_id, team_id, current_user, org_context)
