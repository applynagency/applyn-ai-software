"""Customer pilot communications service (Sprint 67C)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.integration_readiness.evidence import redact_text
from app.models.customer_pilot import (
    COMMUNICATION_CATEGORIES,
    PilotCommunicationComment,
    PilotCustomerCommunication,
)
from app.models.organization import OrganizationMember
from app.models.pilot import PilotEnrollment, PilotLiveOperation
from app.models.user import User
from app.pilot.communication_templates import PILOT_COMMUNICATION_TEMPLATES, render_template
from app.pilot.customer_portal import notification_payload, sanitize_customer_view
from app.platform.events import DomainEventType, emit_event
from app.repositories.audit import AuditLogRepository
from app.repositories.pilot import PilotEnrollmentRepo
from app.services.pilot import PilotService
from app.services.pilot_notification_delivery import PilotNotificationDeliveryService
from app.tenancy.permissions import can_manage_organization, can_read_resources, can_write_resources

_COMMENT_RATE_LIMIT = 10
_COMMENT_WINDOW = timedelta(hours=1)
_HTML_PATTERN = re.compile(r"<[^>]+>")


class CustomerPilotCommunicationsService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.pilot = PilotService(session)
        self.enrollments = PilotEnrollmentRepo(session)
        self.audit = AuditLogRepository(session)
        self.deliveries = PilotNotificationDeliveryService(session)

    def _ensure_read(self, user: User, org_context: OrgContext) -> str:
        if not can_read_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    def _ensure_customer_admin(self, user: User, org_context: OrgContext) -> str:
        if not can_manage_organization(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Customer admin permissions required")
        return org_context.requires_organization

    def _ensure_operator(self, user: User, org_context: OrgContext) -> str:
        if not can_write_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Platform operator permissions required")
        return org_context.requires_organization

    def _redact_message(self, text: str) -> str:
        cleaned = _HTML_PATTERN.sub("", text or "")
        return redact_text(cleaned.strip())

    def _communication_view(self, row: PilotCustomerCommunication) -> dict:
        return sanitize_customer_view({
            "id": row.id,
            "category": row.category,
            "status": row.status,
            "title": row.title,
            "body": row.body,
            "deep_link": row.deep_link,
            "operation_id": row.operation_id,
            "sent_at": row.sent_at.isoformat() if row.sent_at else None,
            "acknowledgements": row.acknowledgements or [],
            "recipient_count": len(row.recipient_user_ids or []),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        })

    async def list_communications(self, user: User, org_context: OrgContext) -> list[dict]:
        organization_id = self._ensure_read(user, org_context)
        rows = list((await self.session.execute(
            select(PilotCustomerCommunication).where(
                PilotCustomerCommunication.organization_id == organization_id,
                PilotCustomerCommunication.status == "SENT",
            ).order_by(PilotCustomerCommunication.sent_at.desc()).limit(100),
        )).scalars().all())
        return [self._communication_view(r) for r in rows]

    async def get_communication(self, user: User, org_context: OrgContext, communication_id: str) -> dict:
        organization_id = self._ensure_read(user, org_context)
        row = await self.session.get(PilotCustomerCommunication, communication_id)
        if not row or row.organization_id != organization_id or row.status != "SENT":
            raise NotFoundError("PilotCustomerCommunication", communication_id)
        return self._communication_view(row)

    async def acknowledge(self, user: User, org_context: OrgContext, communication_id: str) -> dict:
        organization_id = self._ensure_customer_admin(user, org_context)
        row = await self.session.get(PilotCustomerCommunication, communication_id)
        if not row or row.organization_id != organization_id or row.status != "SENT":
            raise NotFoundError("PilotCustomerCommunication", communication_id)
        acks = list(row.acknowledgements or [])
        if not any(a.get("user_id") == user.id for a in acks):
            acks.append({"user_id": user.id, "at": datetime.now(UTC).isoformat()})
            row.acknowledgements = acks
            await self.session.flush()
            await self.audit.log(
                action="customer_pilot.communication_acknowledged",
                resource_type="pilot_customer_communication",
                resource_id=row.id,
                user_id=user.id,
                organization_id=organization_id,
                details={"communication_id": row.id},
            )
            await emit_event(
                self.session, DomainEventType.CUSTOMER_PILOT_COMMUNICATION_ACKNOWLEDGED,
                organization_id=organization_id,
                actor_id=user.id,
                payload=sanitize_customer_view({"communication_id": row.id}),
            )
        return self._communication_view(row)

    async def add_comment(
        self, user: User, org_context: OrgContext, communication_id: str, *, body: str,
    ) -> dict:
        organization_id = self._ensure_customer_admin(user, org_context)
        row = await self.session.get(PilotCustomerCommunication, communication_id)
        if not row or row.organization_id != organization_id or row.status != "SENT":
            raise NotFoundError("PilotCustomerCommunication", communication_id)
        if not body or not body.strip():
            raise ValidationError("Comment body is required")
        if len(body) > 2000:
            raise ValidationError("Comment exceeds maximum length")

        since = datetime.now(UTC) - _COMMENT_WINDOW
        recent = (await self.session.execute(
            select(func.count()).select_from(PilotCommunicationComment).where(
                PilotCommunicationComment.organization_id == organization_id,
                PilotCommunicationComment.user_id == user.id,
                PilotCommunicationComment.created_at >= since,
            ),
        )).scalar_one()
        if recent >= _COMMENT_RATE_LIMIT:
            raise ValidationError("Comment rate limit exceeded — try again later")

        comment = PilotCommunicationComment(
            organization_id=organization_id,
            communication_id=communication_id,
            user_id=user.id,
            body=self._redact_message(body)[:2000],
        )
        self.session.add(comment)
        await self.session.flush()
        await self.audit.log(
            action="customer_pilot.comment_added",
            resource_type="pilot_communication_comment",
            resource_id=comment.id,
            user_id=user.id,
            organization_id=organization_id,
            details={"communication_id": communication_id},
        )
        await emit_event(
            self.session, DomainEventType.CUSTOMER_PILOT_COMMENT_ADDED,
            organization_id=organization_id,
            actor_id=user.id,
            payload=sanitize_customer_view({"communication_id": communication_id}),
        )
        return {"id": comment.id, "body": comment.body, "created_at": comment.created_at.isoformat()}

    async def validate_send(
        self,
        organization_id: str,
        *,
        category: str,
        operation_id: str | None,
        body: str,
        title: str,
    ) -> tuple[bool, list[str]]:
        blockers: list[str] = []
        if category not in COMMUNICATION_CATEGORIES:
            blockers.append(f"Invalid category: {category}")

        op = None
        if operation_id:
            op = await self.pilot.live_ops.get_for_org(operation_id, organization_id)
            if not op:
                blockers.append("Operation not found in organization")

        body_lower = (body + title).lower()
        if "verified successfully" in body_lower or "execution succeeded" in body_lower:
            if not op or op.verification_status != "VERIFIED":
                blockers.append("Cannot claim verification success before VERIFIED status")
        if "live execution" in body_lower or "running live" in body_lower:
            mode = (op.source_mode if op else "UNAVAILABLE") or "UNAVAILABLE"
            if mode.upper() not in ("LIVE",):
                blockers.append("Cannot claim live execution when source mode is not LIVE")

        return len(blockers) == 0, blockers

    async def draft_communication(
        self,
        user: User,
        org_context: OrgContext,
        *,
        category: str,
        template_key: str | None,
        operation_id: str | None,
        recipient_user_ids: list[str],
        title: str | None = None,
        body: str | None = None,
        variables: dict[str, str] | None = None,
    ) -> dict:
        organization_id = self._ensure_operator(user, org_context)
        enrollment = await self.enrollments.get_for_org(organization_id)
        if not enrollment:
            raise ValidationError("No pilot enrollment for organization")
        if category not in COMMUNICATION_CATEGORIES:
            raise ValidationError(f"Invalid category: {category}")

        members = set((await self.session.execute(
            select(OrganizationMember.user_id).where(OrganizationMember.organization_id == organization_id),
        )).scalars().all())
        if not recipient_user_ids:
            recipient_user_ids = list(members)
        if not recipient_user_ids:
            raise ValidationError("No recipients available in organization")
        for rid in recipient_user_ids:
            if rid not in members:
                raise ValidationError("Recipient must belong to the same organization")

        rendered = render_template(category, variables=variables)
        final_title = self._redact_message(title or rendered["title"])[:300]
        final_body = self._redact_message(body or rendered["body"])[:4000]
        ok, blockers = await self.validate_send(
            organization_id, category=category, operation_id=operation_id,
            body=final_body, title=final_title,
        )
        if not ok:
            raise ValidationError("; ".join(blockers))

        row = PilotCustomerCommunication(
            organization_id=organization_id,
            enrollment_id=enrollment.id,
            operation_id=operation_id,
            category=category,
            status="DRAFT",
            title=final_title,
            body=final_body,
            template_key=template_key or category,
            deep_link=rendered["deep_link"],
            created_by=user.id,
            recipient_user_ids=recipient_user_ids,
            acknowledgements=[],
            meta={"template_key": template_key or category},
        )
        self.session.add(row)
        await self.session.flush()
        await emit_event(
            self.session, DomainEventType.CUSTOMER_PILOT_COMMUNICATION_DRAFTED,
            organization_id=organization_id,
            actor_id=user.id,
            payload=sanitize_customer_view({"communication_id": row.id, "category": category}),
        )
        return self._communication_view(row)

    async def send_communication(self, user: User, org_context: OrgContext, communication_id: str) -> dict:
        organization_id = self._ensure_operator(user, org_context)
        row = await self.session.get(PilotCustomerCommunication, communication_id)
        if not row or row.organization_id != organization_id:
            raise NotFoundError("PilotCustomerCommunication", communication_id)
        if row.status != "DRAFT":
            raise ValidationError("Only draft communications can be sent")

        ok, blockers = await self.validate_send(
            organization_id, category=row.category, operation_id=row.operation_id,
            body=row.body, title=row.title,
        )
        if not ok:
            raise ValidationError("; ".join(blockers))

        row.status = "SENT"
        row.sent_at = datetime.now(UTC)
        await self.session.flush()

        for user_id in row.recipient_user_ids or []:
            idem = f"comm:{row.id}:{user_id}:in_app"
            await self.deliveries.deliver_in_app(
                organization_id=organization_id,
                user_id=user_id,
                title=row.title[:300],
                body=row.body[:4000],
                action_url=row.deep_link or "/customer-pilot",
                idempotency_key=idem,
                communication_id=row.id,
            )

        await self.audit.log(
            action="pilot.communication_sent",
            resource_type="pilot_customer_communication",
            resource_id=row.id,
            user_id=user.id,
            organization_id=organization_id,
            details={"category": row.category, "operation_id": row.operation_id},
        )
        await emit_event(
            self.session, DomainEventType.CUSTOMER_PILOT_COMMUNICATION_SENT,
            organization_id=organization_id,
            actor_id=user.id,
            payload=sanitize_customer_view({"communication_id": row.id, "category": row.category}),
        )
        return self._communication_view(row)

    async def cancel_communication(self, user: User, org_context: OrgContext, communication_id: str) -> dict:
        organization_id = self._ensure_operator(user, org_context)
        row = await self.session.get(PilotCustomerCommunication, communication_id)
        if not row or row.organization_id != organization_id:
            raise NotFoundError("PilotCustomerCommunication", communication_id)
        if row.status != "DRAFT":
            raise ValidationError("Only draft communications can be cancelled")
        row.status = "CANCELLED"
        row.cancelled_at = datetime.now(UTC)
        await self.session.flush()
        return self._communication_view(row)

    def list_templates(self) -> list[dict]:
        return [
            {"category": cat, **meta}
            for cat, meta in PILOT_COMMUNICATION_TEMPLATES.items()
        ]
