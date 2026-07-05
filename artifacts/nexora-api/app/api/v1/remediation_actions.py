"""API for approval-gated remediation actions (Sprint 41B).

Human approval is mandatory. Execution is only ever attempted after an explicit
approval; an already-decided action returns 409. All lookups are org-scoped
(cross-org → 404).
"""

from fastapi import APIRouter

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.incident import (
    RemediationActionResponse,
    RemediationApprovalListResponse,
    RemediationBindRequest,
    RemediationDecisionRequest,
)
from app.services.remediation_actions import RemediationActionService

router = APIRouter(prefix="/remediation-actions", tags=["Remediation Actions"])


@router.get("/{action_id}", response_model=RemediationActionResponse)
async def get_remediation_action(
    action_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = RemediationActionService(session)
    return await service.get_action(action_id, current_user, org_context)


@router.post("/{action_id}/bind", response_model=RemediationActionResponse)
async def bind_remediation_action(
    action_id: str,
    data: RemediationBindRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = RemediationActionService(session)
    return await service.bind(
        action_id,
        current_user,
        org_context,
        credential_id=data.credential_id,
        environment=data.environment,
        namespace=data.namespace,
        application=data.application,
        target_config=data.target_config,
    )


@router.post("/{action_id}/auto-bind", response_model=RemediationActionResponse)
async def auto_bind_remediation_action(
    action_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = RemediationActionService(session)
    return await service.auto_bind_action(action_id, current_user, org_context)


@router.post("/{action_id}/approve", response_model=RemediationActionResponse)
async def approve_remediation_action(
    action_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    data: RemediationDecisionRequest | None = None,
):
    service = RemediationActionService(session)
    return await service.approve(
        action_id, current_user, org_context, comments=(data.comments if data else None)
    )


@router.post("/{action_id}/reject", response_model=RemediationActionResponse)
async def reject_remediation_action(
    action_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    data: RemediationDecisionRequest | None = None,
):
    service = RemediationActionService(session)
    return await service.reject(
        action_id, current_user, org_context, comments=(data.comments if data else None)
    )


@router.post("/{action_id}/retry", response_model=RemediationActionResponse)
async def retry_remediation_action(
    action_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    data: RemediationDecisionRequest | None = None,
):
    service = RemediationActionService(session)
    return await service.retry(
        action_id, current_user, org_context, comments=(data.comments if data else None)
    )


@router.post("/{action_id}/override", response_model=RemediationActionResponse)
async def override_remediation_action(
    action_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    data: RemediationDecisionRequest | None = None,
):
    service = RemediationActionService(session)
    return await service.override(
        action_id, current_user, org_context, comments=(data.comments if data else None)
    )


@router.post("/{action_id}/pause", response_model=RemediationActionResponse)
async def pause_remediation_action(
    action_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    data: RemediationDecisionRequest | None = None,
):
    service = RemediationActionService(session)
    return await service.pause(
        action_id, current_user, org_context, comments=(data.comments if data else None)
    )


@router.post("/{action_id}/resume", response_model=RemediationActionResponse)
async def resume_remediation_action(
    action_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    data: RemediationDecisionRequest | None = None,
):
    service = RemediationActionService(session)
    return await service.resume(
        action_id, current_user, org_context, comments=(data.comments if data else None)
    )


@router.get("/{action_id}/approvals", response_model=RemediationApprovalListResponse)
async def get_remediation_action_approvals(
    action_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = RemediationActionService(session)
    return await service.list_approvals(action_id, current_user, org_context)
