from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.workflow import (
    WorkflowTemplateApplyRequest,
    WorkflowTemplateApplyResponse,
    WorkflowTemplateListResponse,
    WorkflowTemplateResponse,
)
from app.services.workflow_template import WorkflowTemplateService

router = APIRouter(prefix="/workflow-templates", tags=["Workflow Templates"])


@router.get("", response_model=WorkflowTemplateListResponse)
async def list_workflow_templates(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    include_definition: bool = Query(default=False),
):
    service = WorkflowTemplateService(session)
    return await service.list_templates(
        current_user, org_context, include_definition=include_definition
    )


@router.post("/apply", response_model=WorkflowTemplateApplyResponse, status_code=201)
async def apply_workflow_template(
    data: WorkflowTemplateApplyRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = WorkflowTemplateService(session)
    return await service.apply_template(data, current_user, org_context)


@router.get("/{slug}", response_model=WorkflowTemplateResponse)
async def get_workflow_template(
    slug: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = WorkflowTemplateService(session)
    return await service.get_template(slug, current_user, org_context)
