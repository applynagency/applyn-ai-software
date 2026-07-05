"""API for Custom AI Team Agents (Sprint 37A).

Note: the prefix is ``/ai-team-agents`` (not ``/ai-agents``) because the
internal agent-builder feature already owns ``/v1/ai-agents``. These endpoints
manage the customer-facing AI Agents that belong to a Custom AI Team.
"""

from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.core.config import settings
from app.schemas.ai_team import (
    AITeamAgentCreate,
    AITeamAgentExecuteRequest,
    AITeamAgentExecuteResponse,
    AITeamAgentListResponse,
    AITeamAgentMemoryCreate,
    AITeamAgentMemoryListResponse,
    AITeamAgentMemoryResponse,
    AITeamAgentMemoryUpdate,
    AITeamAgentResponse,
    AITeamAgentRunListResponse,
    AITeamAgentUpdate,
    AITeamToolAssignRequest,
    AITeamToolListResponse,
)
from app.services.ai_team import AITeamService
from app.services.ai_team_tools import AITeamToolService

router = APIRouter(prefix="/ai-team-agents", tags=["AI Team Agents"])


@router.get("", response_model=AITeamAgentListResponse)
async def list_ai_team_agents(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    team_id: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    service = AITeamService(session)
    return await service.list_agents(
        current_user,
        org_context,
        team_id=team_id,
        is_active=is_active,
        offset=offset,
        limit=limit,
    )


@router.post("", response_model=AITeamAgentResponse, status_code=201)
async def create_ai_team_agent(
    data: AITeamAgentCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamService(session)
    return await service.create_agent(data, current_user, org_context)


@router.get("/{agent_id}", response_model=AITeamAgentResponse)
async def get_ai_team_agent(
    agent_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamService(session)
    return await service.get_agent(agent_id, current_user, org_context)


@router.put("/{agent_id}", response_model=AITeamAgentResponse)
async def update_ai_team_agent(
    agent_id: str,
    data: AITeamAgentUpdate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamService(session)
    return await service.update_agent(agent_id, data, current_user, org_context)


@router.delete("/{agent_id}", status_code=204)
async def delete_ai_team_agent(
    agent_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamService(session)
    await service.delete_agent(agent_id, current_user, org_context)


@router.post("/{agent_id}/execute", response_model=AITeamAgentExecuteResponse)
async def execute_ai_team_agent(
    agent_id: str,
    data: AITeamAgentExecuteRequest,
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
            "agent_id": agent_id, "prompt": data.prompt,
        }
        job = await submit_job(
            session, task_name="run_ai_team_agent", job_type=JobType.AI_TEAM_AGENT,
            organization_id=org_id, user_id=current_user.id, params=kwargs, task_kwargs=kwargs,
        )
        return accepted_response(job)
    service = AITeamService(session)
    return await service.execute_agent(agent_id, data.prompt, current_user, org_context)


@router.get("/{agent_id}/runs", response_model=AITeamAgentRunListResponse)
async def list_ai_team_agent_runs(
    agent_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    service = AITeamService(session)
    return await service.list_agent_runs(
        agent_id, current_user, org_context, offset=offset, limit=limit
    )


# ----------------------------------------------------- agent memory (39A)
@router.get("/{agent_id}/memory", response_model=AITeamAgentMemoryListResponse)
async def list_ai_team_agent_memory(
    agent_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    memory_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
):
    service = AITeamService(session)
    return await service.list_agent_memories(
        agent_id,
        current_user,
        org_context,
        memory_type=memory_type,
        search=search,
        offset=offset,
        limit=limit,
    )


@router.post("/{agent_id}/memory", response_model=AITeamAgentMemoryResponse, status_code=201)
async def create_ai_team_agent_memory(
    agent_id: str,
    data: AITeamAgentMemoryCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamService(session)
    return await service.create_agent_memory(agent_id, data, current_user, org_context)


@router.put("/memory/{memory_id}", response_model=AITeamAgentMemoryResponse)
async def update_ai_team_agent_memory(
    memory_id: str,
    data: AITeamAgentMemoryUpdate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamService(session)
    return await service.update_memory(memory_id, data, current_user, org_context)


@router.delete("/memory/{memory_id}", status_code=204)
async def delete_ai_team_agent_memory(
    memory_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamService(session)
    await service.delete_memory(memory_id, current_user, org_context)


# ----------------------------------------------------- agent tools (39B)
@router.get("/{agent_id}/tools", response_model=AITeamToolListResponse)
async def list_ai_team_agent_tools(
    agent_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamToolService(session)
    return await service.list_agent_tools(agent_id, current_user, org_context)


@router.post("/{agent_id}/tools", response_model=AITeamToolListResponse)
async def assign_ai_team_agent_tool(
    agent_id: str,
    data: AITeamToolAssignRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamToolService(session)
    return await service.assign_tool(agent_id, data, current_user, org_context)


@router.delete("/{agent_id}/tools/{tool_id}", status_code=204)
async def unassign_ai_team_agent_tool(
    agent_id: str,
    tool_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamToolService(session)
    await service.unassign_tool(agent_id, tool_id, current_user, org_context)
