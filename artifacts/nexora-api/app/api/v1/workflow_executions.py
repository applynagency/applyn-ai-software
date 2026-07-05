
from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.workflow_execution import (
    WorkflowExecutionAuditListResponse,
    WorkflowExecutionListResponse,
    WorkflowExecutionResponse,
    WorkflowExecutionStatusResponse,
)
from app.services.workflow_execution import WorkflowExecutionService

router = APIRouter(prefix="/workflow-executions", tags=["Workflow Executions"])


@router.get("", response_model=WorkflowExecutionListResponse)
async def list_workflow_executions(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    workflow_id: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    service = WorkflowExecutionService(session)
    return await service.list_for_organization(
        current_user, org_context, workflow_id=workflow_id, offset=offset, limit=limit
    )


@router.get("/{execution_id}", response_model=WorkflowExecutionResponse)
async def get_workflow_execution(
    execution_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = WorkflowExecutionService(session)
    return await service.get(execution_id, current_user, org_context)


@router.get("/{execution_id}/status", response_model=WorkflowExecutionStatusResponse)
async def get_workflow_execution_status(
    execution_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = WorkflowExecutionService(session)
    return await service.get_status(execution_id, current_user, org_context)


@router.get("/{execution_id}/audit", response_model=WorkflowExecutionAuditListResponse)
async def list_workflow_execution_audit(
    execution_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = WorkflowExecutionService(session)
    return await service.list_audit_events(execution_id, current_user, org_context)
