"""Sprint 42B — On-Call & Escalation API.

Service ownership, on-call schedules, escalation policies, per-incident
assignment + acknowledgement flow, MTTA/MTTR metrics, and a manual escalation
trigger. Read-only with respect to infrastructure; all writes are org-scoped and
audited. Remediation still requires human approval (handled elsewhere).
"""

from fastapi import APIRouter, HTTPException, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.oncall import (
    AcknowledgeRequest,
    CurrentOnCall,
    EscalationEventResponse,
    EscalationPolicyCreate,
    EscalationPolicyResponse,
    EscalationStepResponse,
    IncidentAssignmentDetailResponse,
    IncidentAssignmentResponse,
    MTTAResponse,
    OnCallScheduleCreate,
    OnCallScheduleResponse,
    ServiceOwnerCreate,
    ServiceOwnerResponse,
    ServiceOwnerUpdate,
    StateUpdateRequest,
)
from app.services.oncall import (
    EscalationEngine,
    IncidentRoutingService,
    OnCallMetricsService,
    OnCallService,
    resolve_current_oncall,
)

router = APIRouter(prefix="/oncall", tags=["On-Call & Escalation"])


def _schedule_response(s) -> OnCallScheduleResponse:
    return OnCallScheduleResponse(
        id=s.id,
        organization_id=s.organization_id,
        name=s.name,
        team=s.team,
        rotation_type=s.rotation_type,
        timezone=s.timezone,
        participants=list(s.participants or []),
        anchor_at=s.anchor_at,
        is_active=s.is_active,
        current_oncall_user_id=resolve_current_oncall(s),
        created_at=s.created_at,
    )


def _policy_response(policy, steps) -> EscalationPolicyResponse:
    return EscalationPolicyResponse(
        id=policy.id,
        organization_id=policy.organization_id,
        name=policy.name,
        service_name=policy.service_name,
        is_active=policy.is_active,
        steps=[EscalationStepResponse.model_validate(st) for st in steps],
        created_at=policy.created_at,
    )


# ------------------------------------------------------------- service owners
@router.post("/service-owners", response_model=ServiceOwnerResponse, status_code=status.HTTP_201_CREATED)
async def create_service_owner(
    data: ServiceOwnerCreate, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    owner = await OnCallService(session).create_service_owner(current_user, org_context, data)
    return ServiceOwnerResponse.model_validate(owner)


@router.get("/service-owners", response_model=list[ServiceOwnerResponse])
async def list_service_owners(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    owners = await OnCallService(session).list_service_owners(current_user, org_context)
    return [ServiceOwnerResponse.model_validate(o) for o in owners]


@router.patch("/service-owners/{owner_id}", response_model=ServiceOwnerResponse)
async def update_service_owner(
    owner_id: str,
    data: ServiceOwnerUpdate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    owner = await OnCallService(session).update_service_owner(current_user, org_context, owner_id, data)
    return ServiceOwnerResponse.model_validate(owner)


@router.delete("/service-owners/{owner_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service_owner(
    owner_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    await OnCallService(session).delete_service_owner(current_user, org_context, owner_id)


# --------------------------------------------------------------- schedules
@router.post("/schedules", response_model=OnCallScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    data: OnCallScheduleCreate, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    s = await OnCallService(session).create_schedule(current_user, org_context, data)
    return _schedule_response(s)


@router.get("/schedules", response_model=list[OnCallScheduleResponse])
async def list_schedules(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    schedules = await OnCallService(session).list_schedules(current_user, org_context)
    return [_schedule_response(s) for s in schedules]


@router.get("/schedules/{schedule_id}", response_model=OnCallScheduleResponse)
async def get_schedule(
    schedule_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    s = await OnCallService(session).get_schedule(current_user, org_context, schedule_id)
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    return _schedule_response(s)


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    await OnCallService(session).delete_schedule(current_user, org_context, schedule_id)


# --------------------------------------------------------------- policies
@router.post("/escalation-policies", response_model=EscalationPolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(
    data: EscalationPolicyCreate, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    svc = OnCallService(session)
    policy = await svc.create_policy(current_user, org_context, data)
    steps = await svc.policy_steps(org_context.requires_organization, policy.id)
    return _policy_response(policy, steps)


@router.get("/escalation-policies", response_model=list[EscalationPolicyResponse])
async def list_policies(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    pairs = await OnCallService(session).list_policies(current_user, org_context)
    return [_policy_response(p, steps) for p, steps in pairs]


@router.delete("/escalation-policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(
    policy_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    await OnCallService(session).delete_policy(current_user, org_context, policy_id)


# --------------------------------------------------------------- current on-call
@router.get("/current", response_model=list[CurrentOnCall])
async def current_oncall(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    pairs = await OnCallService(session).current_oncall(current_user, org_context)
    return [
        CurrentOnCall(schedule_id=s.id, schedule_name=s.name, team=s.team, user_id=uid)
        for s, uid in pairs
    ]


# --------------------------------------------------------------- assignments
@router.get("/incidents/{incident_id}/assignment", response_model=IncidentAssignmentDetailResponse)
async def get_assignment(
    incident_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    assignment, events = await IncidentRoutingService(session).get_assignment(
        current_user, org_context, incident_id
    )
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    resp = IncidentAssignmentDetailResponse.model_validate(assignment)
    resp.escalations = [EscalationEventResponse.model_validate(e) for e in events]
    return resp


@router.post("/incidents/{incident_id}/acknowledge", response_model=IncidentAssignmentResponse)
async def acknowledge(
    incident_id: str,
    data: AcknowledgeRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    assignment = await IncidentRoutingService(session).acknowledge(current_user, org_context, incident_id)
    return IncidentAssignmentResponse.model_validate(assignment)


@router.post("/incidents/{incident_id}/state", response_model=IncidentAssignmentResponse)
async def set_state(
    incident_id: str,
    data: StateUpdateRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    assignment = await IncidentRoutingService(session).set_state(
        current_user, org_context, incident_id, data.state
    )
    return IncidentAssignmentResponse.model_validate(assignment)


# --------------------------------------------------------------- metrics + ops
@router.get("/mtta", response_model=MTTAResponse)
async def mtta(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await OnCallMetricsService(session).metrics(current_user, org_context)
    return MTTAResponse(**data)


@router.post("/escalations/run")
async def run_escalations(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    # Manual/admin trigger of the escalation tick (also runs on a 60s loop).
    _ = org_context.requires_organization
    if not current_user.is_superuser and not org_context.role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    fired = await EscalationEngine(session).process_due()
    return {"escalations_fired": fired}
