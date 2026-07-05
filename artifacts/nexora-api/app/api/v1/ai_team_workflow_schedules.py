"""API for Scheduled Workflow Runs (Sprint 38B).

Customer-facing, additive. Schedules trigger the existing 38A workflow engine;
no internal pipeline behavior is changed.
"""

from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.ai_team import (
    AITeamWorkflowExecuteResponse,
    AITeamWorkflowScheduleCreate,
    AITeamWorkflowScheduleListResponse,
    AITeamWorkflowScheduleResponse,
    AITeamWorkflowScheduleUpdate,
)
from app.services.workflow_scheduler import AITeamWorkflowScheduleService

router = APIRouter(prefix="/ai-team-workflow-schedules", tags=["AI Team Workflow Schedules"])


@router.get("", response_model=AITeamWorkflowScheduleListResponse)
async def list_workflow_schedules(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    workflow_id: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    service = AITeamWorkflowScheduleService(session)
    return await service.list_schedules(
        current_user, org_context, workflow_id=workflow_id, offset=offset, limit=limit
    )


@router.post("", response_model=AITeamWorkflowScheduleResponse, status_code=201)
async def create_workflow_schedule(
    data: AITeamWorkflowScheduleCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamWorkflowScheduleService(session)
    return await service.create_schedule(data, current_user, org_context)


@router.post("/{schedule_id}/run-now", response_model=AITeamWorkflowExecuteResponse)
async def run_workflow_schedule_now(
    schedule_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamWorkflowScheduleService(session)
    return await service.run_now(schedule_id, current_user, org_context)


@router.get("/{schedule_id}", response_model=AITeamWorkflowScheduleResponse)
async def get_workflow_schedule(
    schedule_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamWorkflowScheduleService(session)
    return await service.get_schedule(schedule_id, current_user, org_context)


@router.put("/{schedule_id}", response_model=AITeamWorkflowScheduleResponse)
async def update_workflow_schedule(
    schedule_id: str,
    data: AITeamWorkflowScheduleUpdate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamWorkflowScheduleService(session)
    return await service.update_schedule(schedule_id, data, current_user, org_context)


@router.delete("/{schedule_id}", status_code=204)
async def delete_workflow_schedule(
    schedule_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamWorkflowScheduleService(session)
    await service.delete_schedule(schedule_id, current_user, org_context)
