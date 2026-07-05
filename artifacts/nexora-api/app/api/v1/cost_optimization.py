"""Sprint 43B — Cost Optimization Intelligence API (read-only, advisory).

* POST /v1/cost-optimization/analyze        — run a cost-optimization analysis
* GET  /v1/cost-optimization/analyses       — list analyses (paginated)
* GET  /v1/cost-optimization/analyses/{id}  — get a full analysis report
* GET  /v1/cost-optimization/dashboard      — executive cost dashboard

Advisory only: never scales, deletes, or modifies infrastructure. Org-scoped
and audited.
"""

from fastapi import APIRouter, Query, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.cost_optimization import (
    CostAnalysisListResponse,
    CostAnalyzeRequest,
    CostDashboard,
    CostReport,
)
from app.services.cost_optimization import CostOptimizationService

router = APIRouter(prefix="/cost-optimization", tags=["Cost Optimization"])


@router.post("/analyze", response_model=CostReport, status_code=status.HTTP_201_CREATED)
async def analyze_cost(
    data: CostAnalyzeRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await CostOptimizationService(session).analyze(current_user, org_context, data)


@router.get("/dashboard", response_model=CostDashboard)
async def cost_dashboard(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    return await CostOptimizationService(session).dashboard(current_user, org_context)


@router.get("/analyses", response_model=CostAnalysisListResponse)
async def list_analyses(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    return await CostOptimizationService(session).list_analyses(
        current_user, org_context, offset=offset, limit=limit
    )


@router.get("/analyses/{analysis_id}", response_model=CostReport)
async def get_analysis(
    analysis_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    return await CostOptimizationService(session).get_analysis(current_user, org_context, analysis_id)
