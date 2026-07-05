"""Production pilot readiness API (Sprint 66A/66B)."""

from fastapi import APIRouter, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.pilot.customer_portal import sanitize_customer_view
from app.schemas.customer_pilot import CustomerCommunicationView, OperatorHandoffView, PilotCommunicationDraftRequest
from app.schemas.pilot import PilotDeploymentReadinessView, PilotDryRunStatusView, PilotOperationsReadinessView, PilotSupportBundleExportView
from app.services.customer_pilot_communications import CustomerPilotCommunicationsService
from app.services.pilot_deployment import PilotDeploymentService
from app.services.pilot_notification_delivery import PilotNotificationDeliveryService
from app.services.pilot_operations import PilotOperationsService
from app.schemas.pilot import (
    ConfirmationTokenView,
    ExecutionReadinessView,
    KillSwitchUpdate,
    LiveOperationConfirm,
    LiveOperationCreate,
    LiveOperationListView,
    LiveOperationVerify,
    LiveOperationView,
    OnboardingPathView,
    OperationTemplateView,
    PilotApprovalCreate,
    PilotApprovalDecision,
    PilotApprovalDecisionView,
    PilotApprovalView,
    PilotAssessmentView,
    PilotContactsUpdate,
    PilotClosureRequest,
    PilotClosureView,
    PilotDashboardView,
    PilotDiagnosticsView,
    PilotEvidencePackView,
    PilotExecutionStatusView,
    PilotLaunchReadinessView,
    PilotReadinessView,
    PilotScorecardView,
    PilotStageView,
)
from app.services.pilot import PilotService

router = APIRouter(prefix="/pilot", tags=["Pilot Center"])


def _svc(session: DBSession) -> PilotService:
    return PilotService(session)


@router.get("/readiness", response_model=PilotReadinessView)
async def get_pilot_readiness(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    return await _svc(session).get_readiness(current_user, org_context)


@router.post("/readiness/check", response_model=PilotReadinessView)
async def check_pilot_readiness(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    return await _svc(session).check_readiness(current_user, org_context)


@router.post("/execution/stages/{stage_key}/advance", response_model=PilotStageView)
async def advance_execution_stage(
    stage_key: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await _svc(session).advance_stage(current_user, org_context, stage_key)


@router.get("/execution/status", response_model=PilotExecutionStatusView)
async def get_execution_status(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    return await _svc(session).get_execution_status(current_user, org_context)


@router.get("/operations/catalog", response_model=list[OperationTemplateView])
async def list_operation_catalog(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    return await _svc(session).list_operation_catalog(current_user, org_context)


@router.get("/dashboard", response_model=PilotDashboardView)
async def get_pilot_dashboard(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    return await _svc(session).get_pilot_dashboard(current_user, org_context)


@router.get("/onboarding-paths", response_model=list[OnboardingPathView])
async def list_onboarding_paths(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    return await _svc(session).list_onboarding_paths(current_user, org_context)


@router.post("/onboarding-paths/{path_id}/start")
async def start_onboarding_path(
    path_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    return await _svc(session).start_onboarding_path(current_user, org_context, path_id)


@router.get("/assessment", response_model=PilotAssessmentView | None)
async def get_assessment(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    return await _svc(session).get_assessment(current_user, org_context)


@router.post("/assessment/run", response_model=PilotAssessmentView)
async def run_assessment(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    return await _svc(session).run_assessment(current_user, org_context)


@router.get("/scorecard", response_model=PilotScorecardView)
async def get_scorecard(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    return await _svc(session).get_scorecard(current_user, org_context)


@router.post("/baseline/capture", response_model=PilotScorecardView)
async def capture_baseline(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    return await _svc(session).capture_baseline(current_user, org_context)


@router.post("/baseline/refresh", response_model=PilotScorecardView)
async def refresh_baseline(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    return await _svc(session).refresh_baseline(current_user, org_context)


@router.post("/live-operations/enable")
async def enable_live_operations(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    return await _svc(session).enable_live_operations(current_user, org_context)


@router.post("/live-operations", response_model=LiveOperationView, status_code=status.HTTP_201_CREATED)
async def propose_live_operation(
    payload: LiveOperationCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await _svc(session).propose_live_operation(
        current_user, org_context,
        action=payload.action,
        resource_name=payload.resource_name,
        environment_id=payload.environment_id,
        cluster_id=payload.cluster_id,
        params=payload.params,
        template_id=payload.template_id,
        rollback_plan=payload.rollback_plan,
        namespace=payload.namespace,
        idempotency_key=payload.idempotency_key,
    )


@router.post("/approvals", response_model=PilotApprovalView, status_code=status.HTTP_201_CREATED)
async def create_customer_approval(
    payload: PilotApprovalCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await _svc(session).create_customer_approval(current_user, org_context, payload)


@router.get("/approvals/{approval_id}", response_model=PilotApprovalView)
async def get_customer_approval(
    approval_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await _svc(session).get_customer_approval(current_user, org_context, approval_id)


@router.post("/approvals/{approval_id}/decide", response_model=PilotApprovalDecisionView)
async def decide_customer_approval(
    approval_id: str,
    payload: PilotApprovalDecision,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await _svc(session).decide_customer_approval(
        current_user, org_context, approval_id,
        approve=payload.approve, rationale=payload.rationale,
    )


@router.get("/live-operations", response_model=LiveOperationListView)
async def list_live_operations(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await _svc(session).list_live_operations(current_user, org_context)


@router.get("/live-operations/{operation_id}", response_model=LiveOperationView)
async def get_live_operation(
    operation_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await _svc(session).get_live_operation(current_user, org_context, operation_id)


@router.post(
    "/live-operations/{operation_id}/execution-readiness",
    response_model=ExecutionReadinessView,
)
async def check_execution_readiness(
    operation_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await _svc(session).check_execution_readiness(current_user, org_context, operation_id)


@router.get("/live-operations/{operation_id}/operator-handoff", response_model=OperatorHandoffView)
async def get_operator_handoff(
    operation_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await _svc(session).get_operator_handoff(current_user, org_context, operation_id)


@router.post("/live-operations/{operation_id}/confirm", response_model=LiveOperationView)
async def confirm_live_operation(
    operation_id: str,
    payload: LiveOperationConfirm,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await _svc(session).confirm_live_operation(
        current_user, org_context, operation_id,
        confirmation_token=payload.confirmation_token,
        typed_confirmation=payload.typed_confirmation,
        approved=payload.approved,
    )


@router.post("/live-operations/{operation_id}/confirmation-token", response_model=ConfirmationTokenView)
async def issue_confirmation_token(
    operation_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await _svc(session).issue_confirmation_token(current_user, org_context, operation_id)


@router.post("/live-operations/{operation_id}/verify", response_model=LiveOperationView)
async def verify_live_operation(
    operation_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    payload: LiveOperationVerify | None = None,
):
    body = payload or LiveOperationVerify()
    return await _svc(session).verify_live_operation(
        current_user, org_context, operation_id,
        kubernetes_evidence=body.kubernetes_evidence,
        prometheus_evidence=body.prometheus_evidence,
        events_evidence=body.events_evidence,
        advance_complete=False,
    )


@router.post("/safety/kill-switch")
async def set_kill_switch(
    payload: KillSwitchUpdate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await _svc(session).set_kill_switch(current_user, org_context, enabled=payload.enabled)


@router.get("/support/diagnostics", response_model=PilotDiagnosticsView)
async def get_diagnostics(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    return await _svc(session).get_diagnostics(current_user, org_context)


@router.get("/support/diagnostics/export", response_model=PilotSupportBundleExportView)
async def export_support_diagnostics(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    return await PilotOperationsService(session).export_support_bundle(current_user, org_context)


@router.get("/operations-readiness", response_model=PilotOperationsReadinessView)
async def get_operations_readiness(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    return await PilotOperationsService(session).get_operations_readiness(current_user, org_context)


@router.get("/deployment-readiness", response_model=PilotDeploymentReadinessView)
async def get_deployment_readiness(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    return await PilotDeploymentService(session).get_deployment_readiness(current_user, org_context)


@router.get("/deployment-readiness/dry-run", response_model=PilotDryRunStatusView)
async def get_deployment_dry_run_status(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    from app.tenancy.permissions import can_read_resources
    from app.core.exceptions import ForbiddenError
    if not can_read_resources(org_context.role) and not current_user.is_superuser:
        raise ForbiddenError("Insufficient permissions")
    return PilotDeploymentService(session).get_dry_run_status()


@router.post("/internal/alert-test-signal", include_in_schema=False)
async def set_alert_test_signal(
    current_user: CurrentUser,
    org_context: OrgContextDep,
    value: int = 0,
):
    """Staging-only controlled metric for alert delivery validation (Sprint 67G)."""
    from app.core.config import settings
    from app.core.exceptions import ForbiddenError
    from app.observability import metrics
    from app.tenancy.permissions import can_read_resources

    if not settings.PILOT_ALERT_TEST_ENABLED:
        raise ForbiddenError("Alert test signal disabled")
    if not can_read_resources(org_context.role) and not current_user.is_superuser:
        raise ForbiddenError("Insufficient permissions")
    if value not in (0, 1):
        raise ForbiddenError("value must be 0 or 1")
    metrics.set_customer_pilot_alert_test_signal(value)
    return sanitize_customer_view({"ok": True, "value": value})


@router.get("/launch-readiness", response_model=PilotLaunchReadinessView)
async def get_launch_readiness(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    return await _svc(session).get_launch_readiness(current_user, org_context)


@router.get("/report/export")
async def export_pilot_report(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    return await _svc(session).export_report(current_user, org_context)


@router.get("/evidence-pack/export", response_model=PilotEvidencePackView)
async def export_evidence_pack(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    return await _svc(session).export_evidence_pack(current_user, org_context)


@router.post("/closure", response_model=PilotClosureView)
async def close_internal_pilot(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    payload: PilotClosureRequest | None = None,
):
    body = payload or PilotClosureRequest()
    return await _svc(session).close_internal_pilot(
        current_user, org_context,
        kubernetes_evidence=body.kubernetes_evidence,
        prometheus_evidence=body.prometheus_evidence,
        events_evidence=body.events_evidence,
        integration_evidence=body.integration_evidence,
    )


@router.post("/contacts")
async def update_contacts(
    payload: PilotContactsUpdate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await _svc(session).update_contacts(current_user, org_context, payload)


@router.post("/support/token")
async def issue_support_token(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    return await _svc(session).issue_support_token(current_user, org_context)


def _comm_svc(session: DBSession) -> CustomerPilotCommunicationsService:
    return CustomerPilotCommunicationsService(session)


@router.get("/communications/templates")
async def list_communication_templates(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    return _comm_svc(session).list_templates()


@router.post("/communications/draft", response_model=CustomerCommunicationView)
async def draft_communication(
    payload: PilotCommunicationDraftRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await _comm_svc(session).draft_communication(
        current_user, org_context,
        category=payload.category,
        template_key=payload.template_key,
        operation_id=payload.operation_id,
        recipient_user_ids=payload.recipient_user_ids,
        title=payload.title,
        body=payload.body,
        variables=payload.variables,
    )


@router.post("/communications/{communication_id}/send", response_model=CustomerCommunicationView)
async def send_communication(
    communication_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await _comm_svc(session).send_communication(current_user, org_context, communication_id)


@router.post("/communications/{communication_id}/cancel", response_model=CustomerCommunicationView)
async def cancel_communication(
    communication_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await _comm_svc(session).cancel_communication(current_user, org_context, communication_id)


@router.post("/communications/{communication_id}/deliveries/{delivery_id}/requeue")
async def requeue_notification_delivery(
    communication_id: str,
    delivery_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    from app.tenancy.permissions import can_write_resources
    if not can_write_resources(org_context.role) and not current_user.is_superuser:
        from app.core.exceptions import ForbiddenError
        raise ForbiddenError("Operator permission required")
    return await PilotNotificationDeliveryService(session).requeue(
        current_user, org_context.requires_organization, communication_id, delivery_id,
    )
