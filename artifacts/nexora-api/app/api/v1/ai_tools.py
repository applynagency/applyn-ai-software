"""API for read-only AI Team tool integrations (Sprint 39B)."""

from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.ai_team import (
    AITeamToolConnectionStatusResponse,
    AITeamToolCreate,
    AITeamToolCredentialAttachRequest,
    AITeamToolCredentialResponse,
    AITeamToolExecuteRequest,
    AITeamToolExecuteResponse,
    AITeamToolListResponse,
    AITeamToolResponse,
    AITeamToolRunListResponse,
    AITeamToolUpdate,
    AITeamToolVerifyResponse,
)
from app.services.ai_team_tools import AITeamToolService

router = APIRouter(prefix="/ai-tools", tags=["AI Team Tools"])


@router.get("", response_model=AITeamToolListResponse)
async def list_ai_tools(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    provider: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
):
    service = AITeamToolService(session)
    return await service.list_tools(
        current_user,
        org_context,
        provider=provider,
        is_active=is_active,
        offset=offset,
        limit=limit,
    )


@router.post("", response_model=AITeamToolResponse, status_code=201)
async def create_ai_tool(
    data: AITeamToolCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamToolService(session)
    return await service.create_tool(data, current_user, org_context)


@router.get("/{tool_id}", response_model=AITeamToolResponse)
async def get_ai_tool(
    tool_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamToolService(session)
    return await service.get_tool(tool_id, current_user, org_context)


@router.put("/{tool_id}", response_model=AITeamToolResponse)
async def update_ai_tool(
    tool_id: str,
    data: AITeamToolUpdate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamToolService(session)
    return await service.update_tool(tool_id, data, current_user, org_context)


@router.delete("/{tool_id}", status_code=204)
async def delete_ai_tool(
    tool_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamToolService(session)
    await service.delete_tool(tool_id, current_user, org_context)


@router.post("/{tool_id}/execute", response_model=AITeamToolExecuteResponse)
async def execute_ai_tool(
    tool_id: str,
    data: AITeamToolExecuteRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamToolService(session)
    return await service.execute_tool(tool_id, data, current_user, org_context)


@router.get("/{tool_id}/runs", response_model=AITeamToolRunListResponse)
async def list_ai_tool_runs(
    tool_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    service = AITeamToolService(session)
    return await service.list_runs(
        tool_id, current_user, org_context, offset=offset, limit=limit
    )


# ------------------------------------------------- real credentials (39C)
@router.post("/{tool_id}/credentials", response_model=AITeamToolCredentialResponse, status_code=201)
async def attach_ai_tool_credential(
    tool_id: str,
    data: AITeamToolCredentialAttachRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamToolService(session)
    return await service.attach_credential(tool_id, data, current_user, org_context)


@router.delete("/{tool_id}/credentials/{credential_id}", status_code=204)
async def detach_ai_tool_credential(
    tool_id: str,
    credential_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamToolService(session)
    await service.detach_credential(tool_id, credential_id, current_user, org_context)


@router.get("/{tool_id}/connection-status", response_model=AITeamToolConnectionStatusResponse)
async def ai_tool_connection_status(
    tool_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamToolService(session)
    return await service.connection_status(tool_id, current_user, org_context)


@router.post("/{tool_id}/verify", response_model=AITeamToolVerifyResponse)
async def verify_ai_tool_connection(
    tool_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamToolService(session)
    return await service.verify_connection(tool_id, current_user, org_context)
