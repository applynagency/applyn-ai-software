"""Customer integration onboarding API (Sprint 67A)."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.integration_onboarding import (
    CustomerPilotPrerequisitesView,
    OnboardingAcknowledgeRequest,
    OnboardingCancelRequest,
    OnboardingCredentialsRequest,
    OnboardingEnvironmentUpdate,
    OnboardingLeastPrivilegeGuide,
    OnboardingProviderInfo,
    OnboardingRbacReport,
    OnboardingReadinessView,
    OnboardingSessionCreate,
    OnboardingSessionView,
    OnboardingValidateResponse,
)
from app.services.integration_onboarding import IntegrationOnboardingService

router = APIRouter(prefix="/onboarding/integrations", tags=["Customer Integration Onboarding"])


def _svc(session: DBSession) -> IntegrationOnboardingService:
    return IntegrationOnboardingService(session)


def _to_view(row) -> OnboardingSessionView:
    return OnboardingSessionView.model_validate(row)


@router.get("/providers", response_model=list[OnboardingProviderInfo])
async def list_providers(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    _svc(session)._ensure_read(current_user, org_context)
    return [OnboardingProviderInfo(**p) for p in _svc(session).list_providers()]


@router.post("/sessions", response_model=OnboardingSessionView, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: OnboardingSessionCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    row = await _svc(session).create_session(
        current_user, org_context,
        provider_type=payload.provider_type,
        intended_for_pilot=payload.intended_for_pilot,
    )
    return _to_view(row)


@router.get("/sessions", response_model=list[OnboardingSessionView])
async def list_sessions(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_sessions(current_user, org_context)
    return [_to_view(r) for r in rows]


@router.get("/sessions/{session_id}", response_model=OnboardingSessionView)
async def get_session(
    session_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).get_session(current_user, org_context, session_id)
    return _to_view(row)


@router.put("/sessions/{session_id}/environment", response_model=OnboardingSessionView)
async def update_environment(
    session_id: str,
    payload: OnboardingEnvironmentUpdate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    row = await _svc(session).update_environment(
        current_user, org_context, session_id,
        environment_name=payload.environment_name,
        environment_classification=payload.environment_classification,
        scope=payload.scope,
        intended_for_pilot=payload.intended_for_pilot,
        api_base_url=payload.api_base_url,
    )
    return _to_view(row)


@router.post("/sessions/{session_id}/credentials", response_model=OnboardingSessionView)
async def store_credentials(
    session_id: str,
    payload: OnboardingCredentialsRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    row = await _svc(session).store_credentials(
        current_user, org_context, session_id,
        name=payload.name, secret=payload.secret,
    )
    return _to_view(row)


@router.post("/sessions/{session_id}/validate", response_model=OnboardingValidateResponse)
async def validate_session(
    session_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    result = await _svc(session).validate_session(current_user, org_context, session_id)
    return OnboardingValidateResponse(**result)


@router.get("/sessions/{session_id}/rbac-report", response_model=OnboardingRbacReport)
async def get_rbac_report(
    session_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    report = await _svc(session).get_rbac_report(current_user, org_context, session_id)
    return OnboardingRbacReport(**report)


@router.get("/sessions/{session_id}/least-privilege-guide", response_model=OnboardingLeastPrivilegeGuide)
async def get_least_privilege_guide(
    session_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    guide = await _svc(session).get_least_privilege_guide(current_user, org_context, session_id)
    return OnboardingLeastPrivilegeGuide(**guide)


@router.post("/sessions/{session_id}/acknowledge", response_model=OnboardingSessionView)
async def acknowledge_session(
    session_id: str,
    payload: OnboardingAcknowledgeRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    row = await _svc(session).acknowledge(
        current_user, org_context, session_id,
        acknowledged=payload.acknowledged,
        acknowledgement_note=payload.acknowledgement_note,
    )
    return _to_view(row)


@router.post("/sessions/{session_id}/cancel", response_model=OnboardingSessionView)
async def cancel_session(
    session_id: str,
    payload: OnboardingCancelRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    row = await _svc(session).cancel(
        current_user, org_context, session_id, reason=payload.reason,
    )
    return _to_view(row)


@router.get("/sessions/{session_id}/evidence")
async def get_evidence(
    session_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    return await _svc(session).get_evidence(current_user, org_context, session_id)


@router.get("/readiness", response_model=OnboardingReadinessView)
async def get_readiness(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    result = await _svc(session).get_readiness(current_user, org_context)
    sessions = result.pop("sessions", [])
    return OnboardingReadinessView(
        **result,
        sessions=[_to_view(s) for s in sessions],
    )


@router.get("/customer-pilot-prerequisites", response_model=CustomerPilotPrerequisitesView)
async def get_customer_pilot_prerequisites(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    _svc(session)._ensure_read(current_user, org_context)
    return CustomerPilotPrerequisitesView(**_svc(session).get_customer_pilot_prerequisites())
