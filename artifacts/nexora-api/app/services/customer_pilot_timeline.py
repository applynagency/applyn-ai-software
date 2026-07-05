"""Customer pilot unified timeline service (Sprint 67C)."""

from __future__ import annotations

import base64
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.integration_readiness.evidence import redact_text
from app.models.audit import AuditLog
from app.models.customer_pilot import (
    PilotApprovalPackage,
    PilotApprovalReminderDelivery,
    PilotCloseoutRequest,
    PilotCustomerCommunication,
)
from app.models.organization import Organization
from app.models.pilot import PilotApproval, PilotEnrollment, PilotLiveOperation, PilotStage
from app.models.user import User
from app.pilot.customer_portal import assert_export_safe, sanitize_customer_view
from app.pilot.timeline import (
    CUSTOMER_SAFE_AUDIT_ACTIONS,
    _is_internal_audit,
    build_timeline_event,
    decode_cursor,
    encode_cursor,
    operation_customer_status,
    stage_summary_rows,
    timeline_html,
    timeline_markdown,
)
from app.platform.events import DomainEventType, emit_event
from app.repositories.audit import AuditLogRepository
from app.repositories.pilot import PilotEnrollmentRepo
from app.services.document_export import render_pdf
from app.services.pilot import PilotService
from app.tenancy.permissions import can_read_resources


class CustomerPilotTimelineService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.pilot = PilotService(session)
        self.enrollments = PilotEnrollmentRepo(session)
        self.audit = AuditLogRepository(session)

    def _ensure_read(self, user: User, org_context: OrgContext) -> str:
        if not can_read_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    async def _collect_events(self, organization_id: str, enrollment: PilotEnrollment | None) -> list[dict]:
        events: list[dict] = []
        if not enrollment:
            return events

        stages = await self.pilot.stages.list_for_enrollment(enrollment.id)
        for stage in stages:
            if stage.completed_at:
                events.append(build_timeline_event(
                    event_id=f"stage-{stage.id}",
                    timestamp=stage.completed_at,
                    event_type="STAGE_COMPLETED",
                    title=stage.title,
                    description=f"Pilot stage {stage.stage_key} marked {stage.status}.",
                    status=stage.status,
                    actor_type="PLATFORM_OPERATOR" if stage.owner_id else "SYSTEM",
                    metadata={"stage_key": stage.stage_key, "outcome": stage.outcome},
                    deep_link="/customer-pilot",
                ))

        approvals = list((await self.session.execute(
            select(PilotApproval).where(PilotApproval.organization_id == organization_id),
        )).scalars().all())
        for approval in approvals:
            ts = approval.created_at or datetime.now(UTC)
            events.append(build_timeline_event(
                event_id=f"approval-{approval.id}",
                timestamp=ts,
                event_type="APPROVAL_PACKAGE_CREATED",
                title="Approval package available",
                description="An immutable approval package was created for review.",
                status="AWAITING_CUSTOMER_APPROVAL" if approval.status == "PENDING" else approval.status,
                actor_type="PLATFORM_OPERATOR",
                metadata={"approval_id": approval.id},
                deep_link="/customer-pilot/approval",
                operation_id=approval.operation_id,
            ))
            if approval.approved_at:
                events.append(build_timeline_event(
                    event_id=f"approval-decided-{approval.id}",
                    timestamp=approval.approved_at,
                    event_type="CUSTOMER_APPROVAL_DECIDED",
                    title="Approval granted" if approval.status == "APPROVED" else "Approval decision recorded",
                    description=f"Customer approval status: {approval.status}.",
                    status="CUSTOMER_APPROVED" if approval.status == "APPROVED" else approval.status,
                    actor_type="CUSTOMER_ADMIN",
                    metadata={"approval_id": approval.id},
                    deep_link="/customer-pilot/approval",
                    operation_id=approval.operation_id,
                ))

        packages = list((await self.session.execute(
            select(PilotApprovalPackage).where(PilotApprovalPackage.organization_id == organization_id),
        )).scalars().all())
        for pkg in packages:
            events.append(build_timeline_event(
                event_id=f"pkg-{pkg.id}",
                timestamp=pkg.created_at,
                event_type="APPROVAL_PACKAGE_SNAPSHOT",
                title="Approval package snapshot stored",
                description="Immutable approval package snapshot recorded.",
                status="INFO",
                actor_type="SYSTEM",
                metadata={"payload_hash": pkg.payload_hash},
                deep_link="/customer-pilot/approval",
                operation_id=pkg.operation_id,
            ))

        ops = list((await self.session.execute(
            select(PilotLiveOperation).where(PilotLiveOperation.organization_id == organization_id),
        )).scalars().all())
        for op in ops:
            status = operation_customer_status(op.status, verification_status=op.verification_status)
            events.append(build_timeline_event(
                event_id=f"op-{op.id}",
                timestamp=op.created_at,
                event_type="OPERATION_PROPOSED",
                title="Operation proposed",
                description=f"Proposed operation: {op.action} on {op.resource_name}.",
                status=status,
                actor_type="PLATFORM_OPERATOR",
                metadata={"action": op.action, "resource_name": op.resource_name},
                deep_link="/customer-pilot/operation",
                operation_id=op.id,
            ))
            if op.updated_at and op.updated_at != op.created_at:
                events.append(build_timeline_event(
                    event_id=f"op-status-{op.id}-{op.status}",
                    timestamp=op.updated_at,
                    event_type="OPERATION_STATUS_CHANGED",
                    title="Operation status updated",
                    description=f"Operation status is now {op.status}.",
                    status=status,
                    actor_type="SYSTEM",
                    metadata={"operation_status": op.status},
                    deep_link="/customer-pilot/execution",
                    operation_id=op.id,
                ))

        closeouts = list((await self.session.execute(
            select(PilotCloseoutRequest).where(PilotCloseoutRequest.organization_id == organization_id),
        )).scalars().all())
        for req in closeouts:
            events.append(build_timeline_event(
                event_id=f"closeout-{req.id}",
                timestamp=req.created_at,
                event_type="CLOSEOUT_REQUESTED",
                title="Closeout review requested",
                description="Customer requested pilot closeout review.",
                status="CLOSEOUT_PENDING",
                actor_type="CUSTOMER_ADMIN",
                deep_link="/customer-pilot/closeout",
            ))

        comms = list((await self.session.execute(
            select(PilotCustomerCommunication).where(
                PilotCustomerCommunication.organization_id == organization_id,
                PilotCustomerCommunication.status == "SENT",
            ),
        )).scalars().all())
        for comm in comms:
            events.append(build_timeline_event(
                event_id=f"comm-{comm.id}",
                timestamp=comm.sent_at or comm.created_at,
                event_type=comm.category,
                title=comm.title,
                description=comm.body[:500],
                status="INFO",
                actor_type="PLATFORM_OPERATOR" if comm.created_by else "SYSTEM",
                deep_link=comm.deep_link or "/customer-pilot",
                operation_id=comm.operation_id,
            ))

        reminders = list((await self.session.execute(
            select(PilotApprovalReminderDelivery).where(
                PilotApprovalReminderDelivery.organization_id == organization_id,
            ),
        )).scalars().all())
        for rem in reminders:
            events.append(build_timeline_event(
                event_id=f"reminder-{rem.id}",
                timestamp=rem.delivered_at,
                event_type="APPROVAL_REMINDER" if rem.reminder_type != "EXPIRED" else "APPROVAL_EXPIRED",
                title=f"Approval {rem.reminder_type} reminder" if rem.reminder_type != "EXPIRED" else "Approval expired",
                description="Automated approval reminder or expiry notification.",
                status="AWAITING_CUSTOMER_APPROVAL" if rem.reminder_type != "EXPIRED" else "BLOCKED",
                actor_type="SYSTEM",
                deep_link="/customer-pilot/approval",
                metadata={"reminder_type": rem.reminder_type},
            ))

        from app.models.customer_pilot import PilotNotificationDelivery

        deliveries = list((await self.session.execute(
            select(PilotNotificationDelivery).where(
                PilotNotificationDelivery.organization_id == organization_id,
            ).order_by(PilotNotificationDelivery.queued_at.desc()).limit(50),
        )).scalars().all())
        _delivery_desc = {
            "delivered": "Notification delivered successfully.",
            "sent": "Notification sent.",
            "failed": "Notification delivery failed; your approval status is unchanged.",
            "retrying": "Notification delivery is being retried.",
            "queued": "Notification queued for delivery.",
            "suppressed_by_preference": "Notification suppressed by your preferences.",
            "cancelled": "Notification delivery was cancelled.",
        }
        for d in deliveries:
            events.append(build_timeline_event(
                event_id=f"delivery-{d.id}",
                timestamp=d.delivered_at or d.sent_at or d.queued_at,
                event_type="NOTIFICATION_DELIVERY",
                title=f"Notification {d.status.replace('_', ' ')}",
                description=_delivery_desc.get(d.status, "Notification delivery update."),
                status="INFO",
                actor_type="SYSTEM",
                deep_link="/customer-pilot/communications",
                metadata=sanitize_customer_view({"channel": d.channel, "status": d.status}),
            ))

        audit_rows = list((await self.session.execute(
            select(AuditLog).where(AuditLog.organization_id == organization_id).order_by(AuditLog.created_at.desc()).limit(200),
        )).scalars().all())
        for row in audit_rows:
            if _is_internal_audit(row.action):
                continue
            if row.action in CUSTOMER_SAFE_AUDIT_ACTIONS:
                etype, title, actor = CUSTOMER_SAFE_AUDIT_ACTIONS[row.action]
            elif row.action.startswith("customer_pilot."):
                etype, title, actor = row.action, "Customer pilot activity", "CUSTOMER_ADMIN"
            else:
                continue
            events.append(build_timeline_event(
                event_id=f"audit-{row.id}",
                timestamp=row.created_at,
                event_type=etype,
                title=title,
                description=redact_text(str((row.details or {}).get("summary", title))),
                status="INFO",
                actor_type=actor,
                metadata=sanitize_customer_view(row.details or {}),
                deep_link="/customer-pilot",
                operation_id=(row.details or {}).get("operation_id"),
            ))

        events.sort(key=lambda e: (e["timestamp"], e["id"]), reverse=True)
        return events

    def _filter_events(
        self,
        events: list[dict],
        *,
        status: str | None,
        event_type: str | None,
        operation_id: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[dict]:
        out = events
        if status:
            out = [e for e in out if e.get("status") == status]
        if event_type:
            out = [e for e in out if e.get("event_type") == event_type]
        if operation_id:
            out = [e for e in out if e.get("operation_id") == operation_id]
        if date_from:
            out = [e for e in out if e["timestamp"] >= date_from.isoformat()]
        if date_to:
            out = [e for e in out if e["timestamp"] <= date_to.isoformat()]
        return out

    async def get_timeline(
        self,
        user: User,
        org_context: OrgContext,
        *,
        cursor: str | None = None,
        limit: int = 50,
        status: str | None = None,
        event_type: str | None = None,
        operation_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict:
        organization_id = self._ensure_read(user, org_context)
        enrollment = await self.enrollments.get_for_org(organization_id)
        events = self._filter_events(
            await self._collect_events(organization_id, enrollment),
            status=status,
            event_type=event_type,
            operation_id=operation_id,
            date_from=date_from,
            date_to=date_to,
        )

        if cursor:
            cursor_ts, cursor_id = decode_cursor(cursor)
            cursor_iso = cursor_ts.isoformat()
            events = [
                e for e in events
                if (e["timestamp"], e["id"]) < (cursor_iso, cursor_id)
            ]

        page = events[:limit]
        next_cursor = None
        if len(events) > limit and page:
            last = page[-1]
            next_cursor = encode_cursor(datetime.fromisoformat(last["timestamp"]), last["id"])

        stage_map = {}
        if enrollment:
            stages = await self.pilot.stages.list_for_enrollment(enrollment.id)
            stage_map = {s.stage_key: s for s in stages}

        return sanitize_customer_view({
            "events": page,
            "next_cursor": next_cursor,
            "has_more": next_cursor is not None,
            "stage_summary": stage_summary_rows(stage_map),
            "current_stage": enrollment.current_stage if enrollment else None,
        })

    async def export_timeline(
        self,
        user: User,
        org_context: OrgContext,
        **filters,
    ) -> dict:
        organization_id = self._ensure_read(user, org_context)
        data = await self.get_timeline(user, org_context, limit=500, **filters)
        pack = {"events": data["events"], "stage_summary": data.get("stage_summary", [])}
        try:
            assert_export_safe(pack)
            org = await self.session.get(Organization, organization_id)
            org_name = org.name if org else "Organization"
            md = timeline_markdown(data["events"], organization_name=org_name)
            html = timeline_html(data["events"], organization_name=org_name)
            pdf = base64.b64encode(render_pdf(md)).decode("ascii")
            blocked, reason = False, None
        except ValidationError as exc:
            md, html, pdf = "", "", None
            blocked, reason = True, str(exc)

        await self.audit.log(
            action="customer_pilot.timeline_exported",
            resource_type="customer_pilot_timeline",
            resource_id=organization_id,
            user_id=user.id,
            organization_id=organization_id,
            details={"event_count": len(data["events"])},
        )
        await emit_event(
            self.session, DomainEventType.CUSTOMER_PILOT_TIMELINE_EXPORTED,
            organization_id=organization_id,
            actor_id=user.id,
            payload=sanitize_customer_view({"event_count": len(data["events"])}),
        )
        return {
            "json_payload": pack,
            "markdown": md,
            "html": html,
            "pdf_base64": pdf,
            "redacted": True,
            "export_blocked": blocked,
            "block_reason": reason,
        }
