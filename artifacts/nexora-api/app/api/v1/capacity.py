"""Sprint 43A — Capacity Planning & Forecasting API (read-only, advisory).

* POST /v1/capacity/metrics          — ingest normalized utilization samples
* POST /v1/capacity/forecasts        — create forecast(s) for a scope
* GET  /v1/capacity/forecasts        — list forecasts (paginated)
* GET  /v1/capacity/forecasts/{id}   — get a forecast
* GET  /v1/capacity/dashboard        — capacity overview

Advisory only: never scales, provisions, or mutates infrastructure. Org-scoped
and audited.
"""

from fastapi import APIRouter, Query, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.capacity import (
    CapacityDashboard,
    CapacityMetricIngestRequest,
    CapacityMetricIngestResponse,
    ForecastCreateRequest,
    ForecastListResponse,
    ForecastResponse,
)
from app.services.capacity import CapacityService

router = APIRouter(prefix="/capacity", tags=["Capacity Planning"])


@router.post("/metrics", response_model=CapacityMetricIngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_metrics(
    data: CapacityMetricIngestRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    n = await CapacityService(session).ingest(current_user, org_context, data.samples)
    return CapacityMetricIngestResponse(ingested=n)


@router.post("/forecasts", response_model=list[ForecastResponse], status_code=status.HTTP_201_CREATED)
async def create_forecast(
    data: ForecastCreateRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await CapacityService(session).create_forecast(current_user, org_context, data)


@router.get("/dashboard", response_model=CapacityDashboard)
async def capacity_dashboard(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    return await CapacityService(session).dashboard(current_user, org_context)


@router.get("/forecasts", response_model=ForecastListResponse)
async def list_forecasts(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    rows, total = await CapacityService(session).list_forecasts(
        current_user, org_context, offset=offset, limit=limit
    )
    service = CapacityService(session)
    return ForecastListResponse(
        items=[service._to_response(r) for r in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/forecasts/{forecast_id}", response_model=ForecastResponse)
async def get_forecast(
    forecast_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    return await CapacityService(session).get_forecast(current_user, org_context, forecast_id)
