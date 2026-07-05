"""Sprint 52C — Demo Organization Generator API.

Authenticated users can spin up fully populated demo organizations from an
industry template, list the ones they own, regenerate/reset their data, and
delete them. The requesting user becomes the OWNER of each demo organization,
so it shows up in the normal organization switcher.
"""

from fastapi import APIRouter

from app.auth.dependencies import CurrentUser, DBSession
from app.schemas.demo_organization import (
    DemoOrgCreateRequest,
    DemoOrgListResponse,
    DemoOrgSummary,
    DemoTemplateListResponse,
)
from app.services.demo_organization import DemoOrganizationService

router = APIRouter(prefix="/demo-organizations", tags=["Demo Organizations"])


@router.get("/templates", response_model=DemoTemplateListResponse)
async def list_templates(current_user: CurrentUser, session: DBSession):
    service = DemoOrganizationService(session)
    return DemoTemplateListResponse(templates=service.templates())


@router.post("", response_model=DemoOrgSummary, status_code=201)
async def create_demo_organization(
    data: DemoOrgCreateRequest, current_user: CurrentUser, session: DBSession
):
    service = DemoOrganizationService(session)
    return await service.create(template=data.template, name=data.name, user=current_user)


@router.get("", response_model=DemoOrgListResponse)
async def list_demo_organizations(current_user: CurrentUser, session: DBSession):
    service = DemoOrganizationService(session)
    items = await service.list_for_user(current_user)
    return DemoOrgListResponse(items=items, total=len(items))


@router.post("/{organization_id}/regenerate", response_model=DemoOrgSummary)
async def regenerate_demo_organization(
    organization_id: str, current_user: CurrentUser, session: DBSession
):
    service = DemoOrganizationService(session)
    return await service.regenerate(organization_id=organization_id, user=current_user)


@router.post("/{organization_id}/reset", response_model=DemoOrgSummary)
async def reset_demo_organization(
    organization_id: str, current_user: CurrentUser, session: DBSession
):
    service = DemoOrganizationService(session)
    return await service.reset(organization_id=organization_id, user=current_user)


@router.delete("/{organization_id}", status_code=204)
async def delete_demo_organization(
    organization_id: str, current_user: CurrentUser, session: DBSession
):
    service = DemoOrganizationService(session)
    await service.delete(organization_id=organization_id, user=current_user)
