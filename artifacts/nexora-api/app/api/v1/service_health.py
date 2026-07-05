"""Sprint 42C — Service Health & SLO Intelligence API (read-only analytics).

* POST/GET/PATCH/DELETE /v1/services         — service catalog
* GET    /v1/services/health                 — org-wide health overview
* GET    /v1/services/{id}/health            — full SLO health report
* POST/GET /v1/services/{id}/slos            — SLO definitions
* DELETE /v1/services/slos/{slo_id}          — delete an SLO

All org-scoped; reliability math is computed read-only. SLO access is audited.
"""

from fastapi import APIRouter, HTTPException, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.slo import (
    ServiceCreate,
    ServiceHealthOverview,
    ServiceHealthReport,
    ServiceResponse,
    ServiceSLOCreate,
    ServiceSLOResponse,
    ServiceUpdate,
)
from app.services.service_health import ServiceHealthService

router = APIRouter(prefix="/services", tags=["Service Health & SLO"])


@router.post("", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
async def create_service(
    data: ServiceCreate, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    svc = await ServiceHealthService(session).create_service(current_user, org_context, data)
    return ServiceResponse.model_validate(svc)


@router.get("", response_model=list[ServiceResponse])
async def list_services(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    services = await ServiceHealthService(session).list_services(current_user, org_context)
    return [ServiceResponse.model_validate(s) for s in services]


@router.get("/health", response_model=ServiceHealthOverview)
async def health_overview(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    return await ServiceHealthService(session).overview(current_user, org_context)


@router.delete("/slos/{slo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_slo(
    slo_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    await ServiceHealthService(session).delete_slo(current_user, org_context, slo_id)


@router.get("/{service_id}", response_model=ServiceResponse)
async def get_service(
    service_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    svc = await ServiceHealthService(session).get_service(current_user, org_context, service_id)
    if svc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return ServiceResponse.model_validate(svc)


@router.patch("/{service_id}", response_model=ServiceResponse)
async def update_service(
    service_id: str,
    data: ServiceUpdate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    svc = await ServiceHealthService(session).update_service(current_user, org_context, service_id, data)
    return ServiceResponse.model_validate(svc)


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(
    service_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    await ServiceHealthService(session).delete_service(current_user, org_context, service_id)


@router.get("/{service_id}/health", response_model=ServiceHealthReport)
async def service_health(
    service_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    return await ServiceHealthService(session).health_report(current_user, org_context, service_id)


@router.post("/{service_id}/slos", response_model=ServiceSLOResponse, status_code=status.HTTP_201_CREATED)
async def create_slo(
    service_id: str,
    data: ServiceSLOCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    slo = await ServiceHealthService(session).create_slo(current_user, org_context, service_id, data)
    return ServiceSLOResponse.model_validate(slo)


@router.get("/{service_id}/slos", response_model=list[ServiceSLOResponse])
async def list_slos(
    service_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    slos = await ServiceHealthService(session).list_slos(current_user, org_context, service_id)
    return [ServiceSLOResponse.model_validate(s) for s in slos]
