"""API for Reusable Team Workflows (Sprint 38A).

Customer-facing, additive. Reuses the Sprint 37C collaboration engine for
execution; does not touch the internal APPYLN pipeline or the internal
``/v1/workflows`` feature.
"""

from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.core.config import settings
from app.schemas.ai_team import (
    AITeamWorkflowCreate,
    AITeamWorkflowExecuteRequest,
    AITeamWorkflowExecuteResponse,
    AITeamWorkflowListResponse,
    AITeamWorkflowResponse,
    AITeamWorkflowRunListResponse,
    AITeamWorkflowUpdate,
)
from app.services.ai_team_workflow import AITeamWorkflowService

router = APIRouter(prefix="/ai-team-workflows", tags=["AI Team Workflows"])


@router.get("", response_model=AITeamWorkflowListResponse)
async def list_ai_team_workflows(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    team_id: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    service = AITeamWorkflowService(session)
    return await service.list_workflows(
        current_user, org_context, team_id=team_id, is_active=is_active,
        offset=offset, limit=limit,
    )


@router.post("", response_model=AITeamWorkflowResponse, status_code=201)
async def create_ai_team_workflow(
    data: AITeamWorkflowCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamWorkflowService(session)
    return await service.create_workflow(data, current_user, org_context)


@router.post("/{workflow_id}/execute", response_model=AITeamWorkflowExecuteResponse)
async def execute_ai_team_workflow(
    workflow_id: str,
    data: AITeamWorkflowExecuteRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    if settings.JOB_QUEUE_ENABLED:
        from app.jobs.submit import accepted_response, submit_job
        from app.models.job import JobType

        org_id = org_context.requires_organization
        kwargs = {
            "organization_id": org_id, "user_id": current_user.id,
            "workflow_id": workflow_id, "prompt": data.prompt,
        }
        job = await submit_job(
            session, task_name="run_ai_team_workflow", job_type=JobType.AI_TEAM_WORKFLOW,
            organization_id=org_id, user_id=current_user.id, params=kwargs, task_kwargs=kwargs,
        )
        return accepted_response(job)
    service = AITeamWorkflowService(session)
    return await service.execute_workflow(workflow_id, data.prompt, current_user, org_context)


@router.get("/{workflow_id}/runs", response_model=AITeamWorkflowRunListResponse)
async def list_ai_team_workflow_runs(
    workflow_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    service = AITeamWorkflowService(session)
    return await service.list_workflow_runs(
        workflow_id, current_user, org_context, offset=offset, limit=limit
    )


@router.get("/{workflow_id}", response_model=AITeamWorkflowResponse)
async def get_ai_team_workflow(
    workflow_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamWorkflowService(session)
    return await service.get_workflow(workflow_id, current_user, org_context)


@router.put("/{workflow_id}", response_model=AITeamWorkflowResponse)
async def update_ai_team_workflow(
    workflow_id: str,
    data: AITeamWorkflowUpdate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamWorkflowService(session)
    return await service.update_workflow(workflow_id, data, current_user, org_context)


@router.delete("/{workflow_id}", status_code=204)
async def delete_ai_team_workflow(
    workflow_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamWorkflowService(session)
    await service.delete_workflow(workflow_id, current_user, org_context)
