"""API for the Incident Investigation Engine (Sprint 40A).

Read-only: an AI Team agent investigates an incident across connected tools and
returns a synthesized Root Cause Analysis. No remediation or mutations.
"""

from fastapi import APIRouter, Query, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.incident import (
    IncidentChangesResponse,
    IncidentDetailResponse,
    IncidentEvidenceResponse,
    IncidentInvestigateRequest,
    IncidentListResponse,
    IncidentRecommendationsResponse,
    IncidentResponse,
    IncidentTimelineResponse,
    NotificationChannelsResponse,
    NotificationChannelsUpdateRequest,
    RemediationActionListResponse,
)
from app.schemas.incident_lifecycle import (
    CommandCenterResponse,
    IncidentAssignRequest,
    IncidentCommentRequest,
    IncidentCommentResponse,
    IncidentEscalateRequest,
    IncidentNoteRequest,
    IncidentTaskCreateRequest,
    IncidentTaskResponse,
    IncidentTaskUpdateRequest,
    LifecycleEventResponse,
    LifecycleTransitionRequest,
)
from app.services.incident_evidence import IncidentEvidenceService
from app.services.incident_investigation import IncidentInvestigationService
from app.services.incident_lifecycle import IncidentLifecycleService
from app.services.notification_channels import OrgNotificationChannelService
from app.services.remediation_actions import RemediationActionService
from app.tenancy.permissions import can_write_resources

router = APIRouter(prefix="/incidents", tags=["Incident Investigation"])


@router.post("/investigate", response_model=IncidentDetailResponse, status_code=201)
async def investigate_incident(
    data: IncidentInvestigateRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = IncidentInvestigationService(session)
    return await service.investigate(data, current_user, org_context)


@router.get("", response_model=IncidentListResponse)
async def list_incidents(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    service = IncidentInvestigationService(session)
    return await service.list_investigations(
        current_user, org_context, offset=offset, limit=limit
    )


@router.get("/notification-channels", response_model=NotificationChannelsResponse)
async def get_notification_channels(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    org_id = org_context.requires_organization
    return await OrgNotificationChannelService(session).get_channels(org_id)


@router.put("/notification-channels", response_model=NotificationChannelsResponse)
async def update_notification_channels(
    data: NotificationChannelsUpdateRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    if not can_write_resources(org_context.role) and not current_user.is_superuser:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    org_id = org_context.requires_organization
    result = await OrgNotificationChannelService(session).set_channels(
        org_id,
        updated_by=current_user.id,
        slack_webhook_url=data.slack_webhook_url,
        teams_webhook_url=data.teams_webhook_url,
        pagerduty_routing_key=data.pagerduty_routing_key,
        default_channels=data.default_channels,
        clear_slack=data.clear_slack,
        clear_teams=data.clear_teams,
        clear_pagerduty=data.clear_pagerduty,
    )
    await session.commit()
    return result


@router.get("/{investigation_id}", response_model=IncidentDetailResponse)
async def get_incident(
    investigation_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = IncidentInvestigationService(session)
    return await service.get_investigation(investigation_id, current_user, org_context)


@router.get("/{investigation_id}/timeline", response_model=IncidentTimelineResponse)
async def get_incident_timeline(
    investigation_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = IncidentInvestigationService(session)
    return await service.get_timeline(investigation_id, current_user, org_context)


@router.get("/{investigation_id}/changes", response_model=IncidentChangesResponse)
async def get_incident_changes(
    investigation_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = IncidentInvestigationService(session)
    return await service.get_changes(investigation_id, current_user, org_context)


@router.get(
    "/{investigation_id}/recommendations",
    response_model=IncidentRecommendationsResponse,
)
async def get_incident_recommendations(
    investigation_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = IncidentInvestigationService(session)
    return await service.get_recommendations(investigation_id, current_user, org_context)


@router.get("/{investigation_id}/actions", response_model=RemediationActionListResponse)
async def get_incident_actions(
    investigation_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = RemediationActionService(session)
    return await service.list_for_incident(investigation_id, current_user, org_context)


@router.get("/{investigation_id}/evidence", response_model=IncidentEvidenceResponse)
async def get_incident_evidence(
    investigation_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = IncidentEvidenceService(session)
    return await service.get_evidence(investigation_id, current_user, org_context)


# --------------------------------------------------------------------------- #
# Sprint 58A.4 — Complete Incident Lifecycle (command center).
# --------------------------------------------------------------------------- #
@router.get("/{investigation_id}/command-center", response_model=CommandCenterResponse)
async def get_incident_command_center(
    investigation_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await IncidentLifecycleService(session).command_center(
        investigation_id, current_user, org_context
    )


@router.post("/{investigation_id}/transition", response_model=IncidentResponse)
async def transition_incident(
    investigation_id: str,
    data: LifecycleTransitionRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await IncidentLifecycleService(session).transition(
        investigation_id, current_user, org_context, to_status=data.status, note=data.note
    )


@router.post("/{investigation_id}/acknowledge", response_model=IncidentResponse)
async def acknowledge_incident(
    investigation_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    data: IncidentNoteRequest | None = None,
):
    return await IncidentLifecycleService(session).acknowledge(
        investigation_id, current_user, org_context, note=(data.note if data else None)
    )


@router.post("/{investigation_id}/assign", response_model=IncidentResponse)
async def assign_incident(
    investigation_id: str,
    data: IncidentAssignRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await IncidentLifecycleService(session).assign(
        investigation_id, current_user, org_context,
        assignee_id=data.assignee_id, note=data.note,
    )


@router.post("/{investigation_id}/escalate", response_model=IncidentResponse)
async def escalate_incident(
    investigation_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    data: IncidentEscalateRequest | None = None,
):
    return await IncidentLifecycleService(session).escalate(
        investigation_id, current_user, org_context,
        reason=(data.reason if data else None),
        run_escalation=(data.run_escalation if data else False),
    )


@router.get("/{investigation_id}/events", response_model=list[LifecycleEventResponse])
async def list_incident_events(
    investigation_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await IncidentLifecycleService(session).list_events(
        investigation_id, current_user, org_context
    )


@router.get("/{investigation_id}/comments", response_model=list[IncidentCommentResponse])
async def list_incident_comments(
    investigation_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await IncidentLifecycleService(session).list_comments(
        investigation_id, current_user, org_context
    )


@router.post(
    "/{investigation_id}/comments",
    response_model=IncidentCommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_incident_comment(
    investigation_id: str,
    data: IncidentCommentRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await IncidentLifecycleService(session).add_comment(
        investigation_id, current_user, org_context, body=data.body
    )


@router.get("/{investigation_id}/tasks", response_model=list[IncidentTaskResponse])
async def list_incident_tasks(
    investigation_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await IncidentLifecycleService(session).list_tasks(
        investigation_id, current_user, org_context
    )


@router.post(
    "/{investigation_id}/tasks",
    response_model=IncidentTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_incident_task(
    investigation_id: str,
    data: IncidentTaskCreateRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await IncidentLifecycleService(session).create_task(
        investigation_id, current_user, org_context,
        title=data.title, description=data.description, assignee_id=data.assignee_id,
    )


@router.patch(
    "/{investigation_id}/tasks/{task_id}", response_model=IncidentTaskResponse
)
async def update_incident_task(
    investigation_id: str,
    task_id: str,
    data: IncidentTaskUpdateRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await IncidentLifecycleService(session).update_task(
        investigation_id, task_id, current_user, org_context,
        title=data.title, description=data.description,
        status=data.status, assignee_id=data.assignee_id,
    )

