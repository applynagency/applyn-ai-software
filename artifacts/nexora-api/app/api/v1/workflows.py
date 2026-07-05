
from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.models.workflow import WorkflowStatus
from app.schemas.workflow import (
    ExecutionPlanResponse,
    WorkflowAuditListResponse,
    WorkflowCreate,
    WorkflowDuplicateResponse,
    WorkflowListResponse,
    WorkflowResponse,
    WorkflowRuleCreate,
    WorkflowRuleResponse,
    WorkflowStageCreate,
    WorkflowStageResponse,
    WorkflowUpdate,
)
from app.schemas.workflow_execution import (
    WorkflowExecuteRequest,
    WorkflowExecutionResponse,
)
from app.services.workflow import WorkflowService
from app.services.workflow_execution import WorkflowExecutionService
from app.services.workflow_stage import WorkflowStageService
from app.workflows.resolution import WorkflowResolutionService

router = APIRouter(prefix="/workflows", tags=["Workflows"])


@router.get("", response_model=WorkflowListResponse)
async def list_workflows(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    status: WorkflowStatus | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    service = WorkflowService(session)
    return await service.list_for_organization(
        current_user, org_context, status=status, offset=offset, limit=limit
    )


@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    data: WorkflowCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = WorkflowService(session)
    return await service.create(data, current_user, org_context)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = WorkflowService(session)
    return await service.get(workflow_id, current_user, org_context)


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str,
    data: WorkflowUpdate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = WorkflowService(session)
    return await service.update(workflow_id, data, current_user, org_context)


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = WorkflowService(session)
    await service.delete(workflow_id, current_user, org_context)


@router.post("/{workflow_id}/duplicate", response_model=WorkflowDuplicateResponse)
async def duplicate_workflow(
    workflow_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = WorkflowService(session)
    return await service.duplicate(workflow_id, current_user, org_context)


@router.post("/{workflow_id}/archive", response_model=WorkflowResponse)
async def archive_workflow(
    workflow_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = WorkflowService(session)
    return await service.archive(workflow_id, current_user, org_context)


@router.post("/{workflow_id}/stages", response_model=WorkflowStageResponse, status_code=201)
async def create_stage(
    workflow_id: str,
    data: WorkflowStageCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = WorkflowStageService(session)
    return await service.create(workflow_id, data, current_user, org_context)


@router.post("/{workflow_id}/rules", response_model=WorkflowRuleResponse, status_code=201)
async def create_rule(
    workflow_id: str,
    data: WorkflowRuleCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = WorkflowStageService(session)
    return await service.create_rule(workflow_id, data, current_user, org_context)


@router.get("/{workflow_id}/execution-plan", response_model=ExecutionPlanResponse)
async def get_execution_plan(
    workflow_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    from app.tenancy.permissions import can_read_workflows

    if not current_user.is_superuser and (
        not org_context.role or not can_read_workflows(org_context.role)
    ):
        from app.core.exceptions import ForbiddenError

        raise ForbiddenError()
    service = WorkflowResolutionService(session)
    return await service.resolve(workflow_id, org_context)


@router.get("/{workflow_id}/audit", response_model=WorkflowAuditListResponse)
async def list_workflow_audit(
    workflow_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = WorkflowService(session)
    return await service.list_audit_events(workflow_id, current_user, org_context)


@router.post("/{workflow_id}/execute", response_model=WorkflowExecutionResponse, status_code=201)
async def execute_workflow(
    workflow_id: str,
    data: WorkflowExecuteRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = WorkflowExecutionService(session)
    return await service.execute(workflow_id, data, current_user, org_context)
