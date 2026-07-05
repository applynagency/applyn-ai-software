from fastapi import APIRouter

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.ai_agent import (
    AIAgentInputResponse,
    AIAgentInputUpdate,
    AIAgentOutputResponse,
    AIAgentOutputUpdate,
    AIAgentResponsibilityResponse,
    AIAgentResponsibilityUpdate,
)
from app.services.ai_agent_component import AIAgentComponentService

router = APIRouter(tags=["AI Agent Components"])


@router.put("/ai-agent-inputs/{input_id}", response_model=AIAgentInputResponse)
async def update_agent_input(
    input_id: str,
    data: AIAgentInputUpdate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AIAgentComponentService(session)
    return await service.update_input(input_id, data, current_user, org_context)


@router.delete("/ai-agent-inputs/{input_id}", status_code=204)
async def delete_agent_input(
    input_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AIAgentComponentService(session)
    await service.delete_input(input_id, current_user, org_context)


@router.put("/ai-agent-outputs/{output_id}", response_model=AIAgentOutputResponse)
async def update_agent_output(
    output_id: str,
    data: AIAgentOutputUpdate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AIAgentComponentService(session)
    return await service.update_output(output_id, data, current_user, org_context)


@router.delete("/ai-agent-outputs/{output_id}", status_code=204)
async def delete_agent_output(
    output_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AIAgentComponentService(session)
    await service.delete_output(output_id, current_user, org_context)


@router.put("/ai-agent-responsibilities/{responsibility_id}", response_model=AIAgentResponsibilityResponse)
async def update_agent_responsibility(
    responsibility_id: str,
    data: AIAgentResponsibilityUpdate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AIAgentComponentService(session)
    return await service.update_responsibility(
        responsibility_id, data, current_user, org_context
    )


@router.delete("/ai-agent-responsibilities/{responsibility_id}", status_code=204)
async def delete_agent_responsibility(
    responsibility_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AIAgentComponentService(session)
    await service.delete_responsibility(responsibility_id, current_user, org_context)
