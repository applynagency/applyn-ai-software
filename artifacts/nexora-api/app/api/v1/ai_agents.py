
from fastapi import APIRouter, Query

from app.ai_agents.resolution import AgentResolutionService
from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.models.ai_agent import AIAgentStatus
from app.schemas.ai_agent import (
    AIAgentAssignmentCreate,
    AIAgentAssignmentResponse,
    AIAgentAuditListResponse,
    AIAgentCreate,
    AIAgentDuplicateResponse,
    AIAgentInputCreate,
    AIAgentInputResponse,
    AIAgentListResponse,
    AIAgentOutputCreate,
    AIAgentOutputResponse,
    AIAgentResponse,
    AIAgentResponsibilityCreate,
    AIAgentResponsibilityResponse,
    AIAgentUpdate,
    StageAgentResolutionResponse,
)
from app.services.ai_agent import AIAgentService
from app.services.ai_agent_component import AIAgentComponentService

router = APIRouter(prefix="/ai-agents", tags=["AI Agents"])


@router.get("/stages/{workflow_stage_id}/resolution", response_model=StageAgentResolutionResponse)
async def resolve_stage_agents(
    workflow_stage_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    from app.core.exceptions import ForbiddenError
    from app.tenancy.permissions import can_read_ai_agents

    if not current_user.is_superuser and (
        not org_context.role or not can_read_ai_agents(org_context.role)
    ):
        raise ForbiddenError()
    service = AgentResolutionService(session)
    return await service.resolve(workflow_stage_id, org_context)


@router.get("", response_model=AIAgentListResponse)
async def list_ai_agents(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    status: AIAgentStatus | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    service = AIAgentService(session)
    return await service.list_for_organization(
        current_user, org_context, status=status, offset=offset, limit=limit
    )


@router.post("", response_model=AIAgentResponse, status_code=201)
async def create_ai_agent(
    data: AIAgentCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AIAgentService(session)
    return await service.create(data, current_user, org_context)


@router.get("/{agent_id}", response_model=AIAgentResponse)
async def get_ai_agent(
    agent_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AIAgentService(session)
    return await service.get(agent_id, current_user, org_context)


@router.put("/{agent_id}", response_model=AIAgentResponse)
async def update_ai_agent(
    agent_id: str,
    data: AIAgentUpdate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AIAgentService(session)
    return await service.update(agent_id, data, current_user, org_context)


@router.delete("/{agent_id}", status_code=204)
async def delete_ai_agent(
    agent_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AIAgentService(session)
    await service.delete(agent_id, current_user, org_context)


@router.post("/{agent_id}/duplicate", response_model=AIAgentDuplicateResponse)
async def duplicate_ai_agent(
    agent_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AIAgentService(session)
    return await service.duplicate(agent_id, current_user, org_context)


@router.post("/{agent_id}/archive", response_model=AIAgentResponse)
async def archive_ai_agent(
    agent_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AIAgentService(session)
    return await service.archive(agent_id, current_user, org_context)


@router.post("/{agent_id}/inputs", response_model=AIAgentInputResponse, status_code=201)
async def create_agent_input(
    agent_id: str,
    data: AIAgentInputCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AIAgentComponentService(session)
    return await service.create_input(agent_id, data, current_user, org_context)


@router.post("/{agent_id}/outputs", response_model=AIAgentOutputResponse, status_code=201)
async def create_agent_output(
    agent_id: str,
    data: AIAgentOutputCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AIAgentComponentService(session)
    return await service.create_output(agent_id, data, current_user, org_context)


@router.post(
    "/{agent_id}/responsibilities",
    response_model=AIAgentResponsibilityResponse,
    status_code=201,
)
async def create_agent_responsibility(
    agent_id: str,
    data: AIAgentResponsibilityCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AIAgentComponentService(session)
    return await service.create_responsibility(agent_id, data, current_user, org_context)


@router.post("/{agent_id}/assign", response_model=AIAgentAssignmentResponse, status_code=201)
async def assign_agent_to_stage(
    agent_id: str,
    data: AIAgentAssignmentCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AIAgentComponentService(session)
    return await service.assign_to_stage(agent_id, data, current_user, org_context)


@router.delete("/{agent_id}/assignments/{assignment_id}", status_code=204)
async def unassign_agent(
    agent_id: str,
    assignment_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AIAgentComponentService(session)
    await service.unassign(agent_id, assignment_id, current_user, org_context)


@router.get("/{agent_id}/audit", response_model=AIAgentAuditListResponse)
async def list_agent_audit(
    agent_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AIAgentService(session)
    return await service.list_audit_events(agent_id, current_user, org_context)
