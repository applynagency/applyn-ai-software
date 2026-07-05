"""Customer pilot portal API (Sprint 67B/67C)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.core.exceptions import NotFoundError
from app.schemas.customer_pilot import (
    CustomerApprovalDecideRequest,
    CustomerApprovalDecideView,
    CustomerApprovalPackageView,
    CustomerCloseoutRequestPayload,
    CustomerCloseoutView,
    CustomerCommunicationCommentPayload,
    CustomerCommunicationView,
    CustomerEvidenceExportView,
    CustomerEvidenceView,
    CustomerExecutionStatusView,
    CustomerNotificationPreferencesUpdate,
    CustomerNotificationPreferencesView,
    CustomerNotificationView,
    CustomerPilotOperationView,
    CustomerPilotOverviewView,
    CustomerPilotTimelineView,
    CustomerTimelineExportView,
    CustomerVerificationView,
)
from app.schemas.pilot import PilotLaunchReadinessView
from app.services.customer_pilot import CustomerPilotService
from app.services.customer_pilot_communications import CustomerPilotCommunicationsService
from app.services.customer_pilot_timeline import CustomerPilotTimelineService

router = APIRouter(prefix="/customer-pilot", tags=["Customer Pilot Portal"])


def _svc(session: DBSession) -> CustomerPilotService:
    return CustomerPilotService(session)


def _timeline_svc(session: DBSession) -> CustomerPilotTimelineService:
    return CustomerPilotTimelineService(session)


def _comm_svc(session: DBSession) -> CustomerPilotCommunicationsService:
    return CustomerPilotCommunicationsService(session)


@router.get("/overview", response_model=CustomerPilotOverviewView)
async def get_overview(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    return await _svc(session).get_overview(current_user, org_context)


@router.get("/readiness", response_model=PilotLaunchReadinessView)
async def get_readiness(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).get_readiness(current_user, org_context)
    return PilotLaunchReadinessView(**{k: v for k, v in data.items() if k in PilotLaunchReadinessView.model_fields})


@router.get("/timeline", response_model=CustomerPilotTimelineView)
async def get_timeline(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    status: str | None = None,
    event_type: str | None = None,
    operation_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    return await _timeline_svc(session).get_timeline(
        current_user, org_context,
        cursor=cursor, limit=limit, status=status, event_type=event_type,
        operation_id=operation_id, date_from=date_from, date_to=date_to,
    )


@router.get("/timeline/export", response_model=CustomerTimelineExportView)
async def export_timeline(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    status: str | None = None,
    event_type: str | None = None,
    operation_id: str | None = None,
):
    return await _timeline_svc(session).export_timeline(
        current_user, org_context,
        status=status, event_type=event_type, operation_id=operation_id,
    )


@router.get("/communications", response_model=list[CustomerCommunicationView])
async def list_communications(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    return await _comm_svc(session).list_communications(current_user, org_context)


@router.get("/communications/{communication_id}", response_model=CustomerCommunicationView)
async def get_communication(
    communication_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    return await _comm_svc(session).get_communication(current_user, org_context, communication_id)


@router.post("/communications/{communication_id}/acknowledge", response_model=CustomerCommunicationView)
async def acknowledge_communication(
    communication_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    return await _comm_svc(session).acknowledge(current_user, org_context, communication_id)


@router.post("/communications/{communication_id}/comment")
async def comment_communication(
    communication_id: str,
    payload: CustomerCommunicationCommentPayload,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await _comm_svc(session).add_comment(
        current_user, org_context, communication_id, body=payload.body,
    )


@router.get("/notification-preferences", response_model=CustomerNotificationPreferencesView)
async def get_notification_preferences(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    return await _svc(session).get_notification_preferences(current_user, org_context)


@router.put("/notification-preferences", response_model=CustomerNotificationPreferencesView)
async def update_notification_preferences(
    payload: CustomerNotificationPreferencesUpdate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await _svc(session).update_notification_preferences(
        current_user, org_context,
        in_app_enabled=payload.in_app_enabled,
        email_enabled=payload.email_enabled,
        approval_reminders_enabled=payload.approval_reminders_enabled,
        evidence_ready_enabled=payload.evidence_ready_enabled,
        closeout_notifications_enabled=payload.closeout_notifications_enabled,
        timezone=payload.timezone,
    )


@router.get("/operation", response_model=CustomerPilotOperationView)
async def get_current_operation(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    try:
        return await _svc(session).get_operation(current_user, org_context, None)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="No pilot operation") from exc


@router.get("/operation/{operation_id}", response_model=CustomerPilotOperationView)
async def get_operation(
    operation_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    return await _svc(session).get_operation(current_user, org_context, operation_id)


@router.get("/operation/{operation_id}/approval-package", response_model=CustomerApprovalPackageView)
async def get_approval_package(
    operation_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    return await _svc(session).get_approval_package(current_user, org_context, operation_id)


@router.post("/operation/{operation_id}/approval/decide", response_model=CustomerApprovalDecideView)
async def decide_approval(
    operation_id: str,
    payload: CustomerApprovalDecideRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    result = await _svc(session).decide_approval(
        current_user, org_context, operation_id,
        approver_name=payload.approver_name,
        approver_email=payload.approver_email,
        approve=payload.approve,
        rationale=payload.rationale,
        payload_hash_acknowledged=payload.payload_hash_acknowledged,
        rollback_plan_acknowledged=payload.rollback_plan_acknowledged,
    )
    return CustomerApprovalDecideView(**result)


@router.get("/operation/{operation_id}/execution-status", response_model=CustomerExecutionStatusView)
async def get_execution_status(
    operation_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    return await _svc(session).get_execution_status(current_user, org_context, operation_id)


@router.get("/operation/{operation_id}/verification", response_model=CustomerVerificationView)
async def get_verification(
    operation_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    return await _svc(session).get_verification(current_user, org_context, operation_id)


@router.get("/operation/{operation_id}/evidence", response_model=CustomerEvidenceView)
async def get_evidence(
    operation_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    return await _svc(session).get_evidence(current_user, org_context, operation_id)


@router.get("/operation/{operation_id}/evidence/export", response_model=CustomerEvidenceExportView)
async def export_evidence(
    operation_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    return await _svc(session).export_evidence(current_user, org_context, operation_id)


@router.get("/closeout", response_model=CustomerCloseoutView)
async def get_closeout(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    return await _svc(session).get_closeout(current_user, org_context)


@router.post("/closeout/request", response_model=CustomerCloseoutView)
async def request_closeout(
    payload: CustomerCloseoutRequestPayload,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    result = await _svc(session).request_closeout(
        current_user, org_context,
        signoff_contact=payload.signoff_contact,
        customer_comments=payload.customer_comments,
        outcome_rating=payload.outcome_rating,
        follow_up_requested=payload.follow_up_requested,
        documented_no_operation=payload.documented_no_operation,
    )
    return CustomerCloseoutView(**result)


@router.get("/notifications", response_model=list[CustomerNotificationView])
async def list_notifications(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    notes = await _svc(session).list_notifications(current_user, org_context)
    return [CustomerNotificationView.model_validate(n) for n in notes]


@router.post("/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notification_read(
    notification_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    await _svc(session).mark_notification_read(current_user, org_context, notification_id)
