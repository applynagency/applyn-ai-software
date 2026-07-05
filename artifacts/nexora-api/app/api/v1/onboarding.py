"""Sprint 47C - Guided Setup Wizard API.

* POST /v1/onboarding/start                - start or resume the wizard
* GET  /v1/onboarding/{id}                  - progress, steps, missing steps, recommendations
* POST /v1/onboarding/{id}/step             - mark/save a step (resume-later state)
* POST /v1/onboarding/{id}/complete         - finish onboarding + provision default team
* POST /v1/onboarding/{id}/sample-incident  - generate a sample incident (demo engine)

Org-scoped & audited. The single onboarding experience for the platform.
"""

from fastapi import APIRouter, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.onboarding import (
    OnboardingCompleteResponse,
    OnboardingResponse,
    SampleIncidentResponse,
    StartRequest,
    StepRequest,
)
from app.services.onboarding import OnboardingService

router = APIRouter(prefix="/onboarding", tags=["Guided Setup Wizard"])


@router.post("/start", response_model=OnboardingResponse, status_code=status.HTTP_201_CREATED)
async def start_onboarding(
    payload: StartRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await OnboardingService(session).start(current_user, org_context, payload)


@router.get("/{session_id}", response_model=OnboardingResponse)
async def get_onboarding(
    session_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await OnboardingService(session).get(current_user, org_context, session_id)


@router.post("/{session_id}/step", response_model=OnboardingResponse)
async def update_onboarding_step(
    session_id: str,
    payload: StepRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await OnboardingService(session).step(current_user, org_context, session_id, payload)


@router.post("/{session_id}/complete", response_model=OnboardingCompleteResponse)
async def complete_onboarding(
    session_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await OnboardingService(session).complete(current_user, org_context, session_id)


@router.post(
    "/{session_id}/sample-incident",
    response_model=SampleIncidentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_sample_incident(
    session_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await OnboardingService(session).generate_sample_incident(
        current_user, org_context, session_id
    )
