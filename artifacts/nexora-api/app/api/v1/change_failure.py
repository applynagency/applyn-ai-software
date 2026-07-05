"""Sprint 44C — Change Failure Prediction API (read-only intelligence).

* POST /v1/change-failure-prediction/analyze     — predict failure for a candidate change
* GET  /v1/change-failure-prediction             — list past predictions
* GET  /v1/change-failure-prediction/dashboard   — org-wide prediction dashboard
* GET  /v1/change-failure-prediction/{id}        — full prediction report

Deterministic, rules-based; never deploys, rolls back, or mutates infrastructure.
Org-scoped and audited.
"""

from fastapi import APIRouter, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.change_failure import (
    ChangeFailureAnalyzeRequest,
    ChangeFailureDashboard,
    ChangeFailurePredictionReport,
    ChangeFailurePredictionSummary,
)
from app.services.change_failure import ChangeFailurePredictionService

router = APIRouter(prefix="/change-failure-prediction", tags=["Change Failure Prediction"])


@router.post("/analyze", response_model=ChangeFailurePredictionReport, status_code=status.HTTP_201_CREATED)
async def analyze_change_failure(
    data: ChangeFailureAnalyzeRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await ChangeFailurePredictionService(session).analyze(current_user, org_context, data)


@router.get("", response_model=list[ChangeFailurePredictionSummary])
async def list_change_failures(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep, limit: int = 100
):
    return await ChangeFailurePredictionService(session).list_predictions(
        current_user, org_context, limit=limit
    )


@router.get("/dashboard", response_model=ChangeFailureDashboard)
async def change_failure_dashboard(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    return await ChangeFailurePredictionService(session).dashboard(current_user, org_context)


@router.get("/{prediction_id}", response_model=ChangeFailurePredictionReport)
async def get_change_failure(
    prediction_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    return await ChangeFailurePredictionService(session).get_prediction(
        current_user, org_context, prediction_id
    )
