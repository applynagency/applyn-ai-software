from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.ai_agent import (
    AIAgentTemplateApplyRequest,
    AIAgentTemplateApplyResponse,
    AIAgentTemplateListResponse,
    AIAgentTemplateResponse,
)
from app.services.ai_agent_template import AIAgentTemplateService

router = APIRouter(prefix="/ai-agent-templates", tags=["AI Agent Templates"])


@router.get("", response_model=AIAgentTemplateListResponse)
async def list_ai_agent_templates(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    include_definition: bool = Query(default=False),
):
    service = AIAgentTemplateService(session)
    return await service.list_templates(
        current_user, org_context, include_definition=include_definition
    )


@router.post("/apply", response_model=AIAgentTemplateApplyResponse, status_code=201)
async def apply_ai_agent_template(
    data: AIAgentTemplateApplyRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AIAgentTemplateService(session)
    return await service.apply_template(data, current_user, org_context)


@router.get("/{slug}", response_model=AIAgentTemplateResponse)
async def get_ai_agent_template(
    slug: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AIAgentTemplateService(session)
    return await service.get_template(slug, current_user, org_context)
