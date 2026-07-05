"""API for Sprint 41D — Deployment Risk Intelligence (read-only).

* GET  /v1/deployment-risk          — risk profile from organization history.
* POST /v1/deployment-risk/analyze  — predict risk for a candidate deployment.

Read-only: no deployment execution, mutations, approvals, or infra changes.
All lookups are organization-scoped.
"""

from fastapi import APIRouter

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.deployment_risk import (
    DeploymentRiskAnalyzeRequest,
    DeploymentRiskReport,
)
from app.services.deployment_risk import DeploymentRiskService

router = APIRouter(prefix="/deployment-risk", tags=["Deployment Risk"])


@router.get("", response_model=DeploymentRiskReport)
async def get_deployment_risk(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    provider: str | None = None,
    environment: str | None = None,
    project_id: str | None = None,
):
    service = DeploymentRiskService(session)
    return await service.analyze(
        current_user,
        org_context,
        provider=provider,
        environment=environment,
        project_id=project_id,
    )


@router.post("/analyze", response_model=DeploymentRiskReport)
async def analyze_deployment_risk(
    data: DeploymentRiskAnalyzeRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = DeploymentRiskService(session)
    return await service.analyze(current_user, org_context, candidate=data)
