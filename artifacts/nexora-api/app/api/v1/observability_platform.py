"""Enterprise Observability Platform REST API (Sprint 65B)."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.observability_platform import (
    AlertIntelligenceView,
    CorrelationRequest,
    CorrelationView,
    DashboardView,
    IntegrationCreate,
    IntegrationView,
    LogQuery,
    MetricQuery,
    ProvidersView,
    SavedSearchCreate,
    SavedSearchView,
    ServiceMapView,
    SLODashboardView,
    TraceQuery,
)
from app.services.observability_platform import ObservabilityPlatformService

router = APIRouter(prefix="/observability", tags=["Enterprise Observability"])


def _svc(session) -> ObservabilityPlatformService:
    return ObservabilityPlatformService(session)


@router.get("/providers", response_model=ProvidersView)
async def list_providers():
    return ProvidersView(**ObservabilityPlatformService.providers())


@router.get("/integrations", response_model=list[IntegrationView])
async def list_integrations(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_integrations(current_user, org_context)
    await session.commit()
    return [IntegrationView.model_validate(r) for r in rows]


@router.post("/integrations", response_model=IntegrationView, status_code=status.HTTP_201_CREATED)
async def create_integration(
    payload: IntegrationCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    row = await _svc(session).create_integration(current_user, org_context, payload)
    await session.commit()
    return IntegrationView.model_validate(row)


@router.post("/metrics/query")
async def query_metrics(
    payload: MetricQuery,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    result = await _svc(session).query_metrics(
        current_user, org_context,
        query=payload.query, window=payload.window, integration_id=payload.integration_id,
    )
    await session.commit()
    return result


@router.get("/metrics/discover")
async def discover_metrics(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    integration_id: str | None = None,
):
    rows = await _svc(session).discover_metrics(current_user, org_context, integration_id)
    await session.commit()
    return {"metrics": rows}


@router.get("/metrics/top")
async def top_metrics(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).top_metrics(current_user, org_context)
    await session.commit()
    return {"metrics": rows}


@router.post("/logs/search")
async def search_logs(
    payload: LogQuery,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    result = await _svc(session).search_logs(
        current_user, org_context,
        query=payload.query, limit=payload.limit, integration_id=payload.integration_id,
    )
    await session.commit()
    return result


@router.get("/logs/saved-searches", response_model=list[SavedSearchView])
async def list_saved_searches(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_saved_searches(current_user, org_context)
    await session.commit()
    return [SavedSearchView.model_validate(r) for r in rows]


@router.post("/logs/saved-searches", response_model=SavedSearchView, status_code=status.HTTP_201_CREATED)
async def create_saved_search(
    payload: SavedSearchCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    row = await _svc(session).create_saved_search(current_user, org_context, payload)
    await session.commit()
    return SavedSearchView.model_validate(row)


@router.post("/traces/search")
async def search_traces(
    payload: TraceQuery,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    result = await _svc(session).search_traces(
        current_user, org_context,
        query=payload.query, limit=payload.limit, integration_id=payload.integration_id,
    )
    await session.commit()
    return result


@router.get("/service-map", response_model=ServiceMapView)
async def service_map(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).service_map(current_user, org_context)
    await session.commit()
    return ServiceMapView(**data)


@router.get("/slo", response_model=SLODashboardView)
async def slo_dashboard(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).slo_dashboard(current_user, org_context)
    await session.commit()
    return SLODashboardView(**data)


@router.post("/slo/evaluate", status_code=status.HTTP_201_CREATED)
async def evaluate_slos(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).evaluate_slos(current_user, org_context)
    await session.commit()
    return {"evaluations": [{"id": r.id, "objective": r.objective, "compliant": r.compliant} for r in rows]}


@router.get("/error-budget")
async def error_budgets(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).error_budgets(current_user, org_context)
    await session.commit()
    return {"budgets": rows}


@router.get("/alerts/intelligence", response_model=AlertIntelligenceView)
async def alert_intelligence(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).alert_intelligence(current_user, org_context)
    await session.commit()
    return AlertIntelligenceView(**data)


@router.post("/correlation", response_model=CorrelationView, status_code=status.HTTP_201_CREATED)
async def correlate(
    payload: CorrelationRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    row = await _svc(session).correlate(
        current_user, org_context,
        title=payload.title, service_name=payload.service_name, incident_id=payload.incident_id,
    )
    await session.commit()
    return CorrelationView.model_validate(row)


@router.get("/correlation", response_model=list[CorrelationView])
async def list_correlations(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_correlations(current_user, org_context)
    await session.commit()
    return [CorrelationView.model_validate(r) for r in rows]


@router.get("/dashboard", response_model=DashboardView)
async def dashboard(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).dashboard(current_user, org_context)
    await session.commit()
    return DashboardView(**data)
