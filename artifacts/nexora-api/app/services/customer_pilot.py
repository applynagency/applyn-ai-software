"""Customer pilot portal service (Sprint 67B) — read-mostly customer workflow."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.integration_readiness.evidence import redact_text
from app.models.customer_pilot import PilotApprovalPackage, PilotCloseoutRequest, PilotNotificationPreference
from app.models.delivery import DeliveryEnvironment
from app.models.organization import Organization
from app.models.pilot import PilotApproval, PilotEnrollment, PilotLiveOperation, PilotStage
from app.models.platform_core import InboxNotification
from app.models.user import User
from app.pilot.approval_package import approval_package_html, approval_package_markdown
from app.pilot.customer_portal import (
    ACTIVE_OPERATION_STATUSES,
    assert_export_safe,
    notification_payload,
    rollback_plan_hash,
    sanitize_customer_view,
)
from app.pilot.evidence_pack import build_evidence_pack, evidence_pack_html, evidence_pack_markdown
from app.pilot.launch_readiness import integration_freshness_ok
from app.platform.events import DomainEventType, emit_event
from app.repositories.audit import AuditLogRepository
from app.repositories.pilot import PilotEnrollmentRepo
from app.services.document_export import render_pdf
from app.services.integration_readiness import IntegrationReadinessService
from app.services.pilot import PilotService
from app.tenancy.permissions import can_manage_organization, can_read_resources


class CustomerPilotService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.pilot = PilotService(session)
        self.enrollments = PilotEnrollmentRepo(session)
        self.readiness_svc = IntegrationReadinessService(session)
        self.audit = AuditLogRepository(session)

    def _ensure_read(self, user: User, org_context: OrgContext) -> str:
        if not can_read_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    def _ensure_customer_admin(self, user: User, org_context: OrgContext) -> str:
        if not can_manage_organization(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Customer admin permissions required")
        return org_context.requires_organization

    async def _enrollment(self, organization_id: str) -> PilotEnrollment | None:
        return await self.enrollments.get_for_org(organization_id)

    async def portal_visible(self, user: User, org_context: OrgContext) -> bool:
        organization_id = self._ensure_read(user, org_context)
        enrollment = await self._enrollment(organization_id)
        if enrollment and enrollment.status not in ("CANCELLED",):
            return True
        return can_manage_organization(org_context.role) or user.is_superuser

    async def _active_operation(self, organization_id: str) -> PilotLiveOperation | None:
        ops = list((await self.session.execute(
            select(PilotLiveOperation).where(
                PilotLiveOperation.organization_id == organization_id,
            ).order_by(PilotLiveOperation.created_at.desc()),
        )).scalars().all())
        for op in ops:
            if op.status in ACTIVE_OPERATION_STATUSES:
                return op
        return ops[0] if ops else None

    async def _reject_production_env(self, environment_id: str | None) -> DeliveryEnvironment | None:
        if not environment_id:
            return None
        env = await self.session.get(DeliveryEnvironment, environment_id)
        if env and (env.tier or "").upper() in ("PRODUCTION", "PROD"):
            raise ValidationError("Production environments are not permitted in customer pilot")
        return env

    async def _notify_admins(
        self, organization_id: str, *, title: str, summary: str, path: str, event_type: str,
    ) -> None:
        from app.models.organization import OrganizationMember

        members = list((await self.session.execute(
            select(OrganizationMember.user_id).where(
                OrganizationMember.organization_id == organization_id,
            ),
        )).scalars().all())
        payload = notification_payload(title=title, summary=summary, path=path, event_type=event_type)
        for user_id in members:
            self.session.add(InboxNotification(
                organization_id=organization_id,
                user_id=user_id,
                title=title[:300],
                body=summary[:4000],
                category="customer_pilot",
                priority="normal",
                action_url=path,
                group_key=event_type,
                meta={"event_type": event_type},
            ))
        await emit_event(
            self.session, DomainEventType.PILOT_BLOCKED,
            organization_id=organization_id,
            payload=payload,
        )

    async def get_overview(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        visible = await self.portal_visible(user, org_context)
        enrollment = await self._enrollment(organization_id)
        op = await self._active_operation(organization_id) if enrollment else None
        env = await self._reject_production_env(op.environment_id) if op else None

        closeout = (await self.session.execute(
            select(PilotCloseoutRequest).where(
                PilotCloseoutRequest.organization_id == organization_id,
            ).order_by(PilotCloseoutRequest.created_at.desc()).limit(1),
        )).scalar_one_or_none()

        integrations = []
        for c in await self.readiness_svc.list_connections(user, org_context):
            integrations.append({
                "provider": c.provider_type,
                "state": c.lifecycle_state,
                "mode": c.provider_mode,
                "fresh": integration_freshness_ok(c.last_validated_at),
            })

        approval_status = None
        if op and op.approval_id:
            approval = await self.pilot.approvals.get_for_org(op.approval_id, organization_id)
            approval_status = approval.status if approval else None

        handoff = None
        if op and approval_status == "APPROVED":
            try:
                handoff = (await self.pilot.get_operator_handoff(user, org_context, op.id)).get("handoff_status")
            except ValidationError:
                handoff = "BLOCKED"

        return sanitize_customer_view({
            "portal_visible": visible,
            "enrollment_id": enrollment.id if enrollment else None,
            "execution_status": enrollment.execution_status if enrollment else None,
            "current_stage": enrollment.current_stage if enrollment else None,
            "scope": {
                "environment_name": env.name if env else None,
                "environment_tier": env.tier if env else None,
                "namespace": (op.params or {}).get("namespace") if op else None,
                "resource_name": op.resource_name if op else None,
            },
            "safety": {
                "operation_limit": enrollment.operation_limit if enrollment else None,
                "operation_count": enrollment.operation_count if enrollment else 0,
                "cooldown_minutes": enrollment.cooldown_minutes if enrollment else None,
                "kill_switch": enrollment.kill_switch if enrollment else False,
            },
            "operation_summary": {
                "id": op.id,
                "action": op.action,
                "status": op.status,
            } if op else None,
            "approval_status": approval_status,
            "execution_label": (op.preflight or {}).get("execution_label") if op else None,
            "verification_status": op.verification_status if op else None,
            "operator_handoff_status": handoff,
            "closeout_status": closeout.status if closeout else None,
            "integration_badges": integrations,
        })

    async def get_readiness(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        launch = await self.pilot.get_launch_readiness(user, org_context)
        from app.services.pilot_operations import PilotOperationsService
        ops_status = await PilotOperationsService(self.session).get_customer_operations_status(
            user, org_context,
        )
        merged = sanitize_customer_view({**launch, "operational_status": ops_status})
        return merged

    async def get_operation(self, user: User, org_context: OrgContext, operation_id: str | None = None) -> dict:
        organization_id = self._ensure_read(user, org_context)
        op = (
            await self.pilot.live_ops.get_for_org(operation_id, organization_id)
            if operation_id else await self._active_operation(organization_id)
        )
        if not op:
            raise NotFoundError("PilotLiveOperation", operation_id or "current")
        env = await self._reject_production_env(op.environment_id)
        return self._operation_view(op, env)

    def _operation_view(self, op: PilotLiveOperation, env: DeliveryEnvironment | None) -> dict:
        return sanitize_customer_view({
            "id": op.id,
            "action": op.action,
            "resource_name": op.resource_name,
            "status": op.status,
            "environment": {"name": env.name if env else None, "tier": env.tier if env else None},
            "scope": {
                "namespace": (op.params or {}).get("namespace"),
                "cluster_id": op.cluster_id,
            },
            "rollback_plan": op.rollback_plan,
            "preflight_summary": {
                k: v for k, v in (op.preflight or {}).items()
                if k in ("resource_name", "namespace", "live_eligible", "execution_label", "proposal_phase")
            },
            "before_state": op.before_state or {},
            "payload_hash": op.payload_hash,
            "approval_id": op.approval_id,
            "verification_status": op.verification_status,
        })

    async def get_approval_package(self, user: User, org_context: OrgContext, operation_id: str) -> dict:
        organization_id = self._ensure_read(user, org_context)
        op = await self.pilot.live_ops.get_for_org(operation_id, organization_id)
        if not op:
            raise NotFoundError("PilotLiveOperation", operation_id)
        await self._reject_production_env(op.environment_id)

        row = (await self.session.execute(
            select(PilotApprovalPackage).where(
                PilotApprovalPackage.operation_id == operation_id,
                PilotApprovalPackage.organization_id == organization_id,
            ).order_by(PilotApprovalPackage.created_at.desc()).limit(1),
        )).scalar_one_or_none()

        if not row:
            raise NotFoundError("PilotApprovalPackage", operation_id)

        pkg = sanitize_customer_view(row.package)
        approval = await self.pilot.approvals.get_for_org(op.approval_id, organization_id) if op.approval_id else None
        return {
            "immutable": True,
            "package": pkg,
            "markdown": approval_package_markdown(pkg),
            "html": approval_package_html(pkg),
            "payload_hash": row.payload_hash,
            "rollback_plan_hash": row.rollback_plan_hash,
            "expires_at": approval.expires_at.isoformat() if approval and approval.expires_at else None,
        }

    async def decide_approval(
        self,
        user: User,
        org_context: OrgContext,
        operation_id: str,
        *,
        approver_name: str,
        approver_email: str,
        approve: bool,
        rationale: str,
        payload_hash_acknowledged: str,
        rollback_plan_acknowledged: bool,
    ) -> dict:
        organization_id = self._ensure_customer_admin(user, org_context)
        op = await self.pilot.live_ops.get_for_org(operation_id, organization_id)
        if not op:
            raise NotFoundError("PilotLiveOperation", operation_id)
        await self._reject_production_env(op.environment_id)
        if not op.approval_id:
            raise ValidationError("No pending approval for this operation")
        if op.payload_hash != payload_hash_acknowledged:
            raise ValidationError("Payload hash acknowledgement does not match current operation")
        if not rollback_plan_acknowledged:
            raise ValidationError("Rollback plan acknowledgement is required")
        if not rationale.strip():
            raise ValidationError("Decision rationale is required")

        approval = await self.pilot.approvals.get_for_org(op.approval_id, organization_id)
        if not approval:
            raise NotFoundError("PilotApproval", op.approval_id)
        if approval.approver_email.lower() != approver_email.strip().lower():
            approval.approver_name = approver_name
            approval.approver_email = approver_email

        result = await self.pilot.decide_customer_approval(
            user, org_context, approval.id,
            approve=approve,
            rationale=redact_text(rationale),
        )

        event_title = "Pilot approval granted" if approve else "Pilot approval rejected"
        await self._notify_admins(
            organization_id,
            title=event_title,
            summary=redact_text(rationale)[:500],
            path="/customer-pilot/approval",
            event_type="customer_pilot_approval_decided",
        )

        handoff_status = None
        if approve:
            try:
                handoff = await self.pilot.get_operator_handoff(user, org_context, operation_id)
                handoff_status = handoff.get("handoff_status")
            except ValidationError:
                handoff_status = "BLOCKED"

        await self.audit.log(
            action="customer_pilot.approval_decided",
            resource_type="pilot_approval",
            resource_id=approval.id,
            user_id=user.id,
            organization_id=organization_id,
            details={
                "operation_id": operation_id,
                "approve": approve,
                "payload_hash": op.payload_hash,
            },
        )

        exec_stage = await self.pilot.stages.get_stage(approval.enrollment_id, "EXECUTE")
        if approve and exec_stage and exec_stage.status == "COMPLETED":
            raise ValidationError("Customer approval must not complete EXECUTE stage")

        return {
            "approval_id": approval.id,
            "operation_id": operation_id,
            "status": result.status,
            "decision_rationale": result.decision_rationale,
            "operator_handoff_status": handoff_status,
        }

    async def get_execution_status(self, user: User, org_context: OrgContext, operation_id: str) -> dict:
        organization_id = self._ensure_read(user, org_context)
        op = await self.pilot.live_ops.get_for_org(operation_id, organization_id)
        if not op:
            raise NotFoundError("PilotLiveOperation", operation_id)
        await self._reject_production_env(op.environment_id)

        ready = False
        gates: dict = {}
        blockers: list[str] = []
        try:
            readiness = await self.pilot.check_execution_readiness(user, org_context, operation_id)
            ready = readiness.ready_for_typed_confirmation
            gates = readiness.gates
            blockers = readiness.blockers
        except ValidationError as exc:
            blockers = [str(exc)]

        return sanitize_customer_view({
            "operation_id": operation_id,
            "status": op.status,
            "verification_status": op.verification_status,
            "source_mode": op.source_mode,
            "gates": gates,
            "blockers": blockers,
            "ready_for_operator_confirmation": ready and op.status == "PENDING_CONFIRMATION",
        })

    async def get_verification(self, user: User, org_context: OrgContext, operation_id: str) -> dict:
        organization_id = self._ensure_read(user, org_context)
        op = await self.pilot.live_ops.get_for_org(operation_id, organization_id)
        if not op:
            raise NotFoundError("PilotLiveOperation", operation_id)
        ver = op.verification or {}
        return sanitize_customer_view({
            "operation_id": operation_id,
            "verification_status": op.verification_status or "PENDING",
            "summary": {k: v for k, v in ver.items() if k not in ("raw", "secret")},
            "kubernetes_summary": ver.get("kubernetes") or ver.get("kubernetes_evidence"),
            "prometheus_summary": ver.get("prometheus") or ver.get("prometheus_evidence"),
            "gaps": ver.get("reasons") or ver.get("gaps") or [],
        })

    async def get_evidence(self, user: User, org_context: OrgContext, operation_id: str) -> dict:
        organization_id = self._ensure_read(user, org_context)
        op = await self.pilot.live_ops.get_for_org(operation_id, organization_id)
        if not op:
            raise NotFoundError("PilotLiveOperation", operation_id)

        approval = None
        if op.approval_id:
            approval = await self.pilot.approvals.get_for_org(op.approval_id, organization_id)

        from app.models.audit import AuditLog
        audit_rows = list((await self.session.execute(
            select(AuditLog).where(
                AuditLog.organization_id == organization_id,
            ).order_by(AuditLog.created_at.desc()).limit(30),
        )).scalars().all())

        timeline = []
        for row in audit_rows:
            if not row.action.startswith(("customer_pilot.", "pilot.")):
                continue
            timeline.append({
                "action": row.action,
                "at": row.created_at.isoformat() if row.created_at else None,
                "details": sanitize_customer_view(row.details or {}),
            })

        evidence = build_evidence_pack(sanitize_customer_view({
            "operation": {
                "id": op.id,
                "action": op.action,
                "status": op.status,
                "before_state": op.before_state,
                "after_state": op.after_state,
                "verification_status": op.verification_status,
                "result_summary": {
                    k: v for k, v in (op.result or {}).items()
                    if k not in ("kubeconfig", "token", "secret")
                },
            },
            "approval": {
                "status": approval.status if approval else None,
                "approver_name": approval.approver_name if approval else None,
            } if approval else None,
            "verification": op.verification or {},
        }))

        return {
            "operation_id": operation_id,
            "evidence": evidence,
            "audit_timeline": timeline,
            "redacted": True,
        }

    async def export_evidence(self, user: User, org_context: OrgContext, operation_id: str) -> dict:
        view = await self.get_evidence(user, org_context, operation_id)
        pack = view["evidence"]
        try:
            assert_export_safe(pack)
            md = evidence_pack_markdown(pack)
            html = evidence_pack_html(pack)
            pdf = base64.b64encode(render_pdf(md)).decode("ascii")
            blocked = False
            reason = None
        except ValidationError as exc:
            md, html, pdf = "", "", None
            blocked = True
            reason = str(exc)

        return {
            "json_payload": pack,
            "markdown": md,
            "html": html,
            "pdf_base64": pdf,
            "redacted": True,
            "export_blocked": blocked,
            "block_reason": reason,
        }

    async def get_closeout(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        eligible, blockers = await self._closeout_eligibility(organization_id)
        req = (await self.session.execute(
            select(PilotCloseoutRequest).where(
                PilotCloseoutRequest.organization_id == organization_id,
            ).order_by(PilotCloseoutRequest.created_at.desc()).limit(1),
        )).scalar_one_or_none()
        return {
            "status": req.status if req else ("ELIGIBLE" if eligible else "BLOCKED"),
            "eligible": eligible,
            "blockers": blockers,
            "request": {
                "id": req.id,
                "status": req.status,
                "signoff_contact": req.signoff_contact,
                "created_at": req.created_at.isoformat() if req.created_at else None,
            } if req else None,
        }

    async def _closeout_eligibility(self, organization_id: str) -> tuple[bool, list[str]]:
        blockers: list[str] = []
        enrollment = await self._enrollment(organization_id)
        if not enrollment:
            return False, ["No pilot enrollment"]

        active = await self._active_operation(organization_id)
        if active and active.status in ACTIVE_OPERATION_STATUSES:
            blockers.append("Active operation in progress")

        pending_approvals = (await self.session.execute(
            select(func.count()).select_from(PilotApproval).where(
                PilotApproval.organization_id == organization_id,
                PilotApproval.status == "PENDING",
            ),
        )).scalar_one()
        if pending_approvals:
            blockers.append("Pending approval exists")

        stages = await self.pilot.stages.list_for_enrollment(enrollment.id)
        for s in stages:
            if s.stage_key == "COMPLETE":
                continue
            if s.stage_key in ("EXECUTE", "VERIFY") and s.status != "COMPLETED":
                if enrollment.operation_count > 0:
                    blockers.append(f"Stage {s.stage_key} not completed")

        ops = list((await self.session.execute(
            select(PilotLiveOperation).where(PilotLiveOperation.organization_id == organization_id),
        )).scalars().all())
        if ops:
            latest = ops[-1]
            if latest.verification_status != "VERIFIED" and enrollment.operation_count > 0:
                blockers.append("Operation not VERIFIED")

        return len(blockers) == 0, blockers

    async def request_closeout(
        self,
        user: User,
        org_context: OrgContext,
        *,
        signoff_contact: str,
        customer_comments: str | None = None,
        outcome_rating: int | None = None,
        follow_up_requested: bool = False,
        documented_no_operation: bool = False,
    ) -> dict:
        organization_id = self._ensure_customer_admin(user, org_context)
        enrollment = await self._enrollment(organization_id)
        if not enrollment:
            raise ValidationError("No pilot enrollment")

        eligible, blockers = await self._closeout_eligibility(organization_id)
        if not eligible and not documented_no_operation:
            return {"status": "BLOCKED", "eligible": False, "blockers": blockers, "request": None}

        req = PilotCloseoutRequest(
            organization_id=organization_id,
            enrollment_id=enrollment.id,
            status="PENDING_OPERATOR_REVIEW",
            outcome_rating=outcome_rating,
            customer_comments=redact_text(customer_comments or "")[:2000],
            signoff_contact=signoff_contact.strip(),
            follow_up_requested=follow_up_requested,
            blockers=blockers,
            requested_by=user.id,
        )
        self.session.add(req)
        await self.session.flush()

        await self._notify_admins(
            organization_id,
            title="Pilot closeout review requested",
            summary="A customer closeout request is pending operator review.",
            path="/customer-pilot/closeout",
            event_type="customer_pilot_closeout_requested",
        )
        await self.audit.log(
            action="customer_pilot.closeout_requested",
            resource_type="pilot_closeout_request",
            resource_id=req.id,
            user_id=user.id,
            organization_id=organization_id,
            details={"signoff_contact": signoff_contact, "blockers": blockers},
        )
        return {
            "status": req.status,
            "eligible": True,
            "blockers": blockers,
            "request": {"id": req.id, "status": req.status},
        }

    async def list_notifications(self, user: User, org_context: OrgContext) -> list[InboxNotification]:
        organization_id = self._ensure_read(user, org_context)
        stmt = select(InboxNotification).where(
            InboxNotification.organization_id == organization_id,
            InboxNotification.user_id == user.id,
            InboxNotification.category == "customer_pilot",
        ).order_by(InboxNotification.created_at.desc()).limit(50)
        return list((await self.session.execute(stmt)).scalars().all())

    async def mark_notification_read(self, user: User, org_context: OrgContext, notification_id: str) -> None:
        organization_id = self._ensure_read(user, org_context)
        note = await self.session.get(InboxNotification, notification_id)
        if not note or note.organization_id != organization_id or note.user_id != user.id:
            raise NotFoundError("InboxNotification", notification_id)
        note.read_at = datetime.now(UTC)
        await self.session.flush()

    async def get_notification_preferences(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        row = (await self.session.execute(
            select(PilotNotificationPreference).where(
                PilotNotificationPreference.organization_id == organization_id,
                PilotNotificationPreference.user_id == user.id,
            ),
        )).scalar_one_or_none()
        if not row:
            return {
                "in_app_enabled": True,
                "email_enabled": False,
                "approval_reminders_enabled": True,
                "evidence_ready_enabled": True,
                "closeout_notifications_enabled": True,
                "timezone": "UTC",
            }
        return {
            "in_app_enabled": row.in_app_enabled,
            "email_enabled": row.email_enabled,
            "approval_reminders_enabled": row.approval_reminders_enabled,
            "evidence_ready_enabled": row.evidence_ready_enabled,
            "closeout_notifications_enabled": row.closeout_notifications_enabled,
            "timezone": row.timezone,
        }

    async def update_notification_preferences(
        self,
        user: User,
        org_context: OrgContext,
        *,
        in_app_enabled: bool | None = None,
        email_enabled: bool | None = None,
        approval_reminders_enabled: bool | None = None,
        evidence_ready_enabled: bool | None = None,
        closeout_notifications_enabled: bool | None = None,
        timezone: str | None = None,
    ) -> dict:
        organization_id = self._ensure_customer_admin(user, org_context)
        row = (await self.session.execute(
            select(PilotNotificationPreference).where(
                PilotNotificationPreference.organization_id == organization_id,
                PilotNotificationPreference.user_id == user.id,
            ),
        )).scalar_one_or_none()
        if not row:
            row = PilotNotificationPreference(
                organization_id=organization_id,
                user_id=user.id,
            )
            self.session.add(row)
        if in_app_enabled is not None:
            row.in_app_enabled = in_app_enabled
        if email_enabled is not None:
            row.email_enabled = email_enabled
        if approval_reminders_enabled is not None:
            row.approval_reminders_enabled = approval_reminders_enabled
        if evidence_ready_enabled is not None:
            row.evidence_ready_enabled = evidence_ready_enabled
        if closeout_notifications_enabled is not None:
            row.closeout_notifications_enabled = closeout_notifications_enabled
        if timezone is not None:
            row.timezone = timezone.strip()[:64] or "UTC"
        await self.session.flush()
        await emit_event(
            self.session, DomainEventType.CUSTOMER_PILOT_NOTIFICATION_PREFERENCE_UPDATED,
            organization_id=organization_id,
            actor_id=user.id,
            payload=sanitize_customer_view({"user_id": user.id}),
        )
        await self.audit.log(
            action="customer_pilot.notification_preferences_updated",
            resource_type="pilot_notification_preference",
            resource_id=row.id,
            user_id=user.id,
            organization_id=organization_id,
            details={"timezone": row.timezone},
        )
        return await self.get_notification_preferences(user, org_context)
