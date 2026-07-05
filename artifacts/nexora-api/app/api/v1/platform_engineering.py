"""Platform Engineering REST API (Sprint 64A)."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.platform_engineering import (
    CatalogItemView,
    CatalogRequestCreate,
    CatalogRequestView,
    ComplianceReportView,
    DashboardView,
    DriftFindingView,
    EnvironmentCreate,
    EnvironmentView,
    GoldenTemplateCreate,
    GoldenTemplateView,
    IaCRepositoryCreate,
    IaCRepositoryView,
    IaCRunCreate,
    IaCRunView,
    IaCStackCreate,
    IaCStackView,
    PlatformTemplateView,
    ProvisionCreate,
    ProvisionView,
    SecretRefCreate,
    SecretRefView,
)
from app.services.platform_engineering import PlatformEngineeringService

router = APIRouter(prefix="/platform-engineering", tags=["Platform Engineering"])


def _svc(session) -> PlatformEngineeringService:
    return PlatformEngineeringService(session)


@router.get("/providers")
async def list_providers():
    return PlatformEngineeringService.supported_providers()


@router.get("/dashboard", response_model=DashboardView)
async def dashboard(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).dashboard(current_user, org_context)
    await session.commit()
    return DashboardView(**data)


# --- IaC --------------------------------------------------------------------
@router.get("/repositories", response_model=list[IaCRepositoryView])
async def list_repositories(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_repositories(current_user, org_context)
    await session.commit()
    return [IaCRepositoryView.model_validate(r) for r in rows]


@router.post("/repositories", response_model=IaCRepositoryView, status_code=status.HTTP_201_CREATED)
async def create_repository(
    payload: IaCRepositoryCreate, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).create_repository(current_user, org_context, payload)
    await session.commit()
    return IaCRepositoryView.model_validate(row)


@router.get("/stacks", response_model=list[IaCStackView])
async def list_stacks(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_stacks(current_user, org_context)
    await session.commit()
    return [IaCStackView.model_validate(r) for r in rows]


@router.post("/stacks", response_model=IaCStackView, status_code=status.HTTP_201_CREATED)
async def create_stack(
    payload: IaCStackCreate, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).create_stack(current_user, org_context, payload)
    await session.commit()
    return IaCStackView.model_validate(row)


@router.get("/runs", response_model=list[IaCRunView])
async def list_runs(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
    stack_id: str | None = Query(None),
):
    rows = await _svc(session).list_runs(current_user, org_context, stack_id=stack_id)
    await session.commit()
    return [IaCRunView.model_validate(r) for r in rows]


@router.post("/stacks/{stack_id}/runs", response_model=IaCRunView, status_code=status.HTTP_201_CREATED)
async def propose_run(
    stack_id: str, payload: IaCRunCreate,
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).propose_run(current_user, org_context, stack_id, payload)
    await session.commit()
    return IaCRunView.model_validate(row)


@router.post("/runs/{run_id}/decide", response_model=IaCRunView)
async def decide_run(
    run_id: str, approved: bool = Query(...),
    current_user: CurrentUser = ..., session: DBSession = ..., org_context: OrgContextDep = ...,
):
    row = await _svc(session).decide_run(current_user, org_context, run_id, approved=approved)
    await session.commit()
    return IaCRunView.model_validate(row)


# --- Templates & environments -----------------------------------------------
@router.get("/templates", response_model=list[PlatformTemplateView])
async def list_templates(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_templates(current_user, org_context)
    await session.commit()
    return [PlatformTemplateView.model_validate(r) for r in rows]


@router.get("/environments", response_model=list[EnvironmentView])
async def list_environments(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_environments(current_user, org_context)
    await session.commit()
    return [EnvironmentView.model_validate(r) for r in rows]


@router.post("/environments", response_model=EnvironmentView, status_code=status.HTTP_201_CREATED)
async def create_environment(
    payload: EnvironmentCreate, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).create_environment(current_user, org_context, payload)
    await session.commit()
    return EnvironmentView.model_validate(row)


@router.post("/environments/{environment_id}/decide", response_model=EnvironmentView)
async def decide_environment(
    environment_id: str, approved: bool = Query(...),
    current_user: CurrentUser = ..., session: DBSession = ..., org_context: OrgContextDep = ...,
):
    row = await _svc(session).approve_environment(
        current_user, org_context, environment_id, approved=approved,
    )
    await session.commit()
    return EnvironmentView.model_validate(row)


# --- Provisioning -----------------------------------------------------------
@router.get("/provisions", response_model=list[ProvisionView])
async def list_provisions(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_provisions(current_user, org_context)
    await session.commit()
    return [ProvisionView.model_validate(r) for r in rows]


@router.post("/provisions", response_model=ProvisionView, status_code=status.HTTP_201_CREATED)
async def start_provision(
    payload: ProvisionCreate, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).start_provision(current_user, org_context, payload)
    await session.commit()
    return ProvisionView.model_validate(row)


@router.post("/provisions/{provision_id}/decide", response_model=ProvisionView)
async def decide_provision(
    provision_id: str, approved: bool = Query(...),
    current_user: CurrentUser = ..., session: DBSession = ..., org_context: OrgContextDep = ...,
):
    row = await _svc(session).decide_provision(
        current_user, org_context, provision_id, approved=approved,
    )
    await session.commit()
    return ProvisionView.model_validate(row)


# --- Secrets ----------------------------------------------------------------
@router.get("/secrets", response_model=list[SecretRefView])
async def list_secrets(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_secret_refs(current_user, org_context)
    await session.commit()
    return [SecretRefView.model_validate(r) for r in rows]


@router.post("/secrets", response_model=SecretRefView, status_code=status.HTTP_201_CREATED)
async def create_secret_ref(
    payload: SecretRefCreate, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).create_secret_ref(current_user, org_context, payload)
    await session.commit()
    return SecretRefView.model_validate(row)


@router.post("/secrets/{ref_id}/rotate", response_model=SecretRefView)
async def rotate_secret(
    ref_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).rotate_secret_ref(current_user, org_context, ref_id)
    await session.commit()
    return SecretRefView.model_validate(row)


@router.delete("/secrets/{ref_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_secret_ref(
    ref_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    await _svc(session).delete_secret_ref(current_user, org_context, ref_id)
    await session.commit()


# --- Catalog ----------------------------------------------------------------
@router.get("/catalog", response_model=list[CatalogItemView])
async def list_catalog(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_catalog(current_user, org_context)
    await session.commit()
    return [CatalogItemView.model_validate(r) for r in rows]


@router.post("/catalog/requests", response_model=CatalogRequestView, status_code=status.HTTP_201_CREATED)
async def request_catalog(
    payload: CatalogRequestCreate, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).request_catalog_item(current_user, org_context, payload)
    await session.commit()
    return CatalogRequestView.model_validate(row)


@router.post("/catalog/requests/{request_id}/decide", response_model=CatalogRequestView)
async def decide_catalog_request(
    request_id: str, approved: bool = Query(...),
    current_user: CurrentUser = ..., session: DBSession = ..., org_context: OrgContextDep = ...,
):
    row = await _svc(session).decide_catalog_request(
        current_user, org_context, request_id, approved=approved,
    )
    await session.commit()
    return CatalogRequestView.model_validate(row)


# --- Golden templates -------------------------------------------------------
@router.get("/golden-templates", response_model=list[GoldenTemplateView])
async def list_golden_templates(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_golden_templates(current_user, org_context)
    await session.commit()
    return [GoldenTemplateView.model_validate(r) for r in rows]


@router.post("/golden-templates", response_model=GoldenTemplateView, status_code=status.HTTP_201_CREATED)
async def create_golden_template(
    payload: GoldenTemplateCreate, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).create_golden_template(current_user, org_context, payload)
    await session.commit()
    return GoldenTemplateView.model_validate(row)


# --- Compliance & drift -----------------------------------------------------
@router.post("/compliance/scan", response_model=ComplianceReportView, status_code=status.HTTP_201_CREATED)
async def run_compliance(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    row = await _svc(session).run_compliance(current_user, org_context)
    await session.commit()
    return ComplianceReportView.model_validate(row)


@router.get("/compliance/latest", response_model=ComplianceReportView | None)
async def latest_compliance(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    row = await _svc(session).latest_compliance(current_user, org_context)
    await session.commit()
    return ComplianceReportView.model_validate(row) if row else None


@router.post("/drift/scan", response_model=list[DriftFindingView])
async def scan_drift(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).scan_drift(current_user, org_context)
    await session.commit()
    return [DriftFindingView.model_validate(r) for r in rows]


@router.get("/drift", response_model=list[DriftFindingView])
async def list_drift(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_drift(current_user, org_context)
    await session.commit()
    return [DriftFindingView.model_validate(r) for r in rows]


@router.post("/drift/{finding_id}/acknowledge", response_model=DriftFindingView)
async def acknowledge_drift(
    finding_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).acknowledge_drift(current_user, org_context, finding_id)
    await session.commit()
    return DriftFindingView.model_validate(row)


@router.get("/ai-context")
async def ai_context(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
    question: str | None = Query(None),
):
    data = await _svc(session).ai_context(current_user, org_context, question=question)
    await session.commit()
    return data
