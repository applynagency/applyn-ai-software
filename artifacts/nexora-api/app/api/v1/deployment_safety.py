"""Sprint 42D — Safe Deployment Intelligence API (advisory, read-only).

* POST /v1/deployment-safety/analyze       — pre-deployment safety report
* GET  /v1/deployment-safety/analyses      — recent analyses
* GET  /v1/deployment-safety/analyses/{id} — a stored analysis (full report)
* GET  /v1/deployment-safety/dashboard     — readiness/blast/strategy summary

Advisory only: never executes, blocks, rolls back, or mutates a deployment. All
lookups are org-scoped and audited.
"""

from fastapi import APIRouter

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.deployment_safety import (
    DeploymentSafetyAnalysisSummary,
    DeploymentSafetyAnalyzeRequest,
    DeploymentSafetyDashboard,
    DeploymentSafetyReport,
)
from app.services.deployment_safety import DeploymentSafetyService

router = APIRouter(prefix="/deployment-safety", tags=["Deployment Safety"])


@router.post("/analyze", response_model=DeploymentSafetyReport)
async def analyze_deployment_safety(
    data: DeploymentSafetyAnalyzeRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await DeploymentSafetyService(session).analyze(current_user, org_context, data)


@router.get("/dashboard", response_model=DeploymentSafetyDashboard)
async def deployment_safety_dashboard(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    return await DeploymentSafetyService(session).dashboard(current_user, org_context)


@router.get("/analyses", response_model=list[DeploymentSafetyAnalysisSummary])
async def list_deployment_safety_analyses(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    rows = await DeploymentSafetyService(session).list_analyses(current_user, org_context)
    return [DeploymentSafetyAnalysisSummary.model_validate(r) for r in rows]


@router.get("/analyses/{analysis_id}", response_model=DeploymentSafetyReport)
async def get_deployment_safety_analysis(
    analysis_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    row = await DeploymentSafetyService(session).get_analysis(current_user, org_context, analysis_id)
    # The full report is stored verbatim in ``details``.
    return DeploymentSafetyReport.model_validate(row.details)
