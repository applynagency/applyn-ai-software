"""Sprint 46A - Reliability Maturity Score Engine API.

* POST /v1/reliability/analyze     - run a new maturity assessment (persisted)
* GET  /v1/reliability             - list past assessments
* GET  /v1/reliability/dashboard   - latest assessment + trend reports
* GET  /v1/reliability/{id}        - get one assessment with category scores

Strictly read-only over platform data; org-scoped and audited. No deployment or
remediation actions are ever taken.
"""

from fastapi import APIRouter, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.reliability_maturity import (
    AssessmentResponse,
    AssessmentSummary,
    ReliabilityDashboard,
)
from app.services.reliability_maturity import ReliabilityMaturityService

router = APIRouter(prefix="/reliability", tags=["Reliability Maturity"])


@router.post("/analyze", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED)
async def analyze(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await ReliabilityMaturityService(session).analyze(current_user, org_context)


@router.get("", response_model=list[AssessmentSummary])
async def list_assessments(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    rows = await ReliabilityMaturityService(session).list(current_user, org_context)
    return [AssessmentSummary.model_validate(r) for r in rows]


@router.get("/dashboard", response_model=ReliabilityDashboard)
async def dashboard(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await ReliabilityMaturityService(session).dashboard(current_user, org_context)


@router.get("/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(
    assessment_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await ReliabilityMaturityService(session).get(current_user, org_context, assessment_id)
