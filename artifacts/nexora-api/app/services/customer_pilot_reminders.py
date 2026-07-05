"""Customer pilot approval reminder scheduler (Sprint 67C)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.integration_readiness.evidence import redact_text
from app.models.customer_pilot import PilotApprovalReminderDelivery, PilotNotificationPreference
from app.models.organization import OrganizationMember
from app.models.pilot import PilotApproval
from app.observability import metrics
from app.pilot.communication_templates import render_template
from app.pilot.customer_portal import notification_payload, sanitize_customer_view
from app.platform.events import DomainEventType, emit_event
from app.repositories.audit import AuditLogRepository
from app.redis.locks import scheduler_lock
from app.services.pilot_notification_delivery import PilotNotificationDeliveryService


class CustomerPilotReminderService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditLogRepository(session)
        self.deliveries = PilotNotificationDeliveryService(session)

    async def _prefs_for_user(self, organization_id: str, user_id: str) -> PilotNotificationPreference | None:
        return (await self.session.execute(
            select(PilotNotificationPreference).where(
                PilotNotificationPreference.organization_id == organization_id,
                PilotNotificationPreference.user_id == user_id,
            ),
        )).scalar_one_or_none()

    async def _already_delivered(self, approval_id: str, reminder_type: str) -> bool:
        row = (await self.session.execute(
            select(PilotApprovalReminderDelivery).where(
                PilotApprovalReminderDelivery.approval_id == approval_id,
                PilotApprovalReminderDelivery.reminder_type == reminder_type,
            ),
        )).scalar_one_or_none()
        return row is not None

    async def _record_delivery(self, organization_id: str, approval_id: str, reminder_type: str) -> None:
        self.session.add(PilotApprovalReminderDelivery(
            organization_id=organization_id,
            approval_id=approval_id,
            reminder_type=reminder_type,
            delivered_at=datetime.now(UTC),
        ))
        await self.session.flush()

    async def _notify_user(
        self,
        organization_id: str,
        user_id: str,
        *,
        title: str,
        body: str,
        path: str,
        event_type: str,
        approval_id: str,
        reminder_type: str,
        email: bool = False,
    ) -> None:
        prefs = await self._prefs_for_user(organization_id, user_id)
        suppressed = bool(
            (prefs and not prefs.in_app_enabled)
            or (prefs and event_type.startswith("approval") and not prefs.approval_reminders_enabled)
        )
        idem = f"reminder:{approval_id}:{reminder_type}:{user_id}:in_app"
        await self.deliveries.deliver_in_app(
            organization_id=organization_id,
            user_id=user_id,
            title=title,
            body=body,
            action_url=path,
            idempotency_key=idem,
            approval_id=approval_id,
            suppressed=suppressed,
        )

        if email and prefs and prefs.email_enabled and settings.SMTP_HOST and not suppressed:
            from app.platform.notifications import NotificationService
            from app.models.user import User
            user = await self.session.get(User, user_id)
            if user and user.email:
                email_idem = f"reminder:{approval_id}:{reminder_type}:{user_id}:email"
                email_delivery = await self.deliveries.get_or_create(
                    organization_id=organization_id,
                    recipient_user_id=user_id,
                    channel="email",
                    idempotency_key=email_idem,
                    approval_id=approval_id,
                )
                if email_delivery.status not in ("sent", "delivered"):
                    try:
                        svc = NotificationService(self.session)
                        await svc.send(
                            channel="email",
                            recipient=user.email,
                            organization_id=organization_id,
                            template_key="customer_pilot_reminder",
                            context={"title": title, "body": body},
                        )
                        await self.deliveries.mark_sent(email_delivery)
                        email_delivery.status = "delivered"
                        email_delivery.delivered_at = datetime.now(UTC)
                        await self.session.flush()
                    except Exception as exc:
                        await self.deliveries.mark_failed(email_delivery, str(exc))

    async def _notify_org_admins(
        self,
        organization_id: str,
        *,
        title: str,
        body: str,
        path: str,
        event_type: str,
        approval: PilotApproval,
        reminder_type: str,
    ) -> None:
        members = list((await self.session.execute(
            select(OrganizationMember.user_id).where(OrganizationMember.organization_id == organization_id),
        )).scalars().all())
        for user_id in members:
            await self._notify_user(
                organization_id, user_id,
                title=title, body=body, path=path, event_type=event_type,
                approval_id=approval.id, reminder_type=reminder_type, email=True,
            )

    async def _send_reminder(self, approval: PilotApproval, reminder_type: str) -> bool:
        if approval.status != "PENDING":
            return False
        if await self._already_delivered(approval.id, reminder_type):
            return False

        rendered = render_template("APPROVAL_REMINDER")
        title = f"{rendered['title']} ({reminder_type})"
        body = rendered["body"]
        await self._notify_org_admins(
            approval.organization_id,
            title=title,
            body=body,
            path="/customer-pilot/approval",
            event_type=f"customer_pilot_approval_reminder_{reminder_type.lower()}",
            approval=approval,
            reminder_type=reminder_type,
        )
        await self._record_delivery(approval.organization_id, approval.id, reminder_type)
        await self.audit.log(
            action="pilot.approval_reminder_sent",
            resource_type="pilot_approval",
            resource_id=approval.id,
            organization_id=approval.organization_id,
            details={"reminder_type": reminder_type},
        )
        await emit_event(
            self.session, DomainEventType.CUSTOMER_PILOT_APPROVAL_REMINDER_SENT,
            organization_id=approval.organization_id,
            payload=sanitize_customer_view({"approval_id": approval.id, "reminder_type": reminder_type}),
            idempotency_key=f"{approval.id}:{reminder_type}",
        )
        metrics.record_customer_pilot_approval_reminder(reminder_type)
        return True

    async def _handle_expiry(self, approval: PilotApproval) -> bool:
        if approval.status != "PENDING":
            return False
        if await self._already_delivered(approval.id, "EXPIRED"):
            return False

        expires = approval.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if datetime.now(UTC) <= expires:
            return False

        approval.status = "EXPIRED"
        from app.observability.metrics import record_pilot_approval_event
        record_pilot_approval_event("expired")

        await self._notify_org_admins(
            approval.organization_id,
            title="Pilot approval expired",
            body="A pending pilot approval has expired. A new approval package is required before execution.",
            path="/customer-pilot/approval",
            event_type="customer_pilot_approval_expired",
            approval=approval,
            reminder_type="EXPIRED",
        )
        await self._record_delivery(approval.organization_id, approval.id, "EXPIRED")
        await self.audit.log(
            action="pilot.approval_expired",
            resource_type="pilot_approval",
            resource_id=approval.id,
            organization_id=approval.organization_id,
            details={"approval_id": approval.id},
        )
        await emit_event(
            self.session, DomainEventType.CUSTOMER_PILOT_APPROVAL_EXPIRED,
            organization_id=approval.organization_id,
            payload=sanitize_customer_view({"approval_id": approval.id}),
            idempotency_key=f"{approval.id}:EXPIRED",
        )
        metrics.record_customer_pilot_approval_expiration()
        return True

    async def run(self) -> dict:
        async with scheduler_lock("customer_pilot_approval_reminders") as token:
            if token is None:
                return {"skipped": True, "reason": "lock_not_acquired"}

            now = datetime.now(UTC)
            sent_24h = sent_1h = expirations = failures = 0

            pending = list((await self.session.execute(
                select(PilotApproval).where(PilotApproval.status == "PENDING"),
            )).scalars().all())

            for approval in pending:
                try:
                    expires = approval.expires_at
                    if expires.tzinfo is None:
                        expires = expires.replace(tzinfo=UTC)
                    remaining = expires - now

                    if remaining <= timedelta(0):
                        if await self._handle_expiry(approval):
                            expirations += 1
                        continue

                    if timedelta(hours=23) < remaining <= timedelta(hours=24):
                        if await self._send_reminder(approval, "24H"):
                            sent_24h += 1
                    elif timedelta(minutes=0) < remaining <= timedelta(hours=1):
                        if await self._send_reminder(approval, "1H"):
                            sent_1h += 1
                except Exception:
                    failures += 1
                    metrics.record_customer_pilot_approval_reminder_failure()

            await self.session.commit()
            return {
                "sent_24h": sent_24h,
                "sent_1h": sent_1h,
                "expirations": expirations,
                "failures": failures,
            }


async def run_customer_pilot_approval_reminders(session: AsyncSession) -> dict:
    result = await CustomerPilotReminderService(session).run()
    from app.services.pilot_operations import PilotOperationsService
    from app.models.job import JobType

    await PilotOperationsService(session).record_scheduler_run(
        JobType.CRON_CUSTOMER_PILOT_APPROVAL_REMINDERS.value, result,
    )
    await session.commit()
    return result
