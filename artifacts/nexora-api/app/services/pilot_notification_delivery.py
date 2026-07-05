"""Pilot notification delivery tracking and retry (Sprint 67D)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.integration_readiness.evidence import redact_text
from app.models.audit import AuditLog
from app.models.customer_pilot import PilotNotificationDelivery
from app.models.pilot import PilotApproval
from app.models.platform_core import InboxNotification
from app.models.user import User
from app.observability import metrics
from app.pilot.customer_portal import sanitize_customer_view
from app.platform.events import DomainEventType, emit_event
from app.repositories.audit import AuditLogRepository

MAX_RETRY_ATTEMPTS = 5
BACKOFF_BASE_SECONDS = 60
_REQUEUE_RATE_LIMIT = 20
_REQUEUE_WINDOW = timedelta(hours=1)


class PilotNotificationDeliveryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditLogRepository(session)

    async def get_or_create(
        self,
        *,
        organization_id: str,
        recipient_user_id: str,
        channel: str,
        idempotency_key: str,
        communication_id: str | None = None,
        approval_id: str | None = None,
        status: str = "queued",
        meta: dict | None = None,
    ) -> PilotNotificationDelivery:
        existing = (await self.session.execute(
            select(PilotNotificationDelivery).where(
                PilotNotificationDelivery.idempotency_key == idempotency_key,
            ),
        )).scalar_one_or_none()
        if existing:
            return existing

        row = PilotNotificationDelivery(
            organization_id=organization_id,
            communication_id=communication_id,
            approval_id=approval_id,
            recipient_user_id=recipient_user_id,
            channel=channel,
            status=status,
            idempotency_key=idempotency_key,
            queued_at=datetime.now(UTC),
            meta=meta or {},
        )
        self.session.add(row)
        await self.session.flush()
        await emit_event(
            self.session, DomainEventType.CUSTOMER_PILOT_NOTIFICATION_QUEUED,
            organization_id=organization_id,
            payload=sanitize_customer_view({"delivery_id": row.id, "channel": channel}),
            idempotency_key=idempotency_key,
        )
        metrics.record_customer_pilot_notification_delivery("queued")
        return row

    async def mark_sent(self, delivery: PilotNotificationDelivery) -> None:
        if delivery.status in ("sent", "delivered"):
            return
        delivery.status = "sent"
        delivery.sent_at = datetime.now(UTC)
        delivery.attempts += 1
        await self.session.flush()
        await emit_event(
            self.session, DomainEventType.CUSTOMER_PILOT_NOTIFICATION_SENT,
            organization_id=delivery.organization_id,
            payload=sanitize_customer_view({"delivery_id": delivery.id}),
        )
        metrics.record_customer_pilot_notification_delivery("sent")

    async def mark_suppressed(self, delivery: PilotNotificationDelivery) -> None:
        delivery.status = "suppressed_by_preference"
        await self.session.flush()
        metrics.record_customer_pilot_notification_delivery("suppressed_by_preference")

    async def mark_failed(self, delivery: PilotNotificationDelivery, error: str) -> None:
        delivery.attempts += 1
        delivery.last_error = redact_text(error)[:500]
        if delivery.attempts >= delivery.max_attempts:
            delivery.status = "failed"
            metrics.record_customer_pilot_notification_failure()
        else:
            delivery.status = "retrying"
            delay = BACKOFF_BASE_SECONDS * (2 ** (delivery.attempts - 1))
            delivery.next_retry_at = datetime.now(UTC) + timedelta(seconds=min(delay, 3600))
            metrics.record_customer_pilot_notification_retry()
            await emit_event(
                self.session, DomainEventType.CUSTOMER_PILOT_NOTIFICATION_RETRIED,
                organization_id=delivery.organization_id,
                payload=sanitize_customer_view({"delivery_id": delivery.id, "attempt": delivery.attempts}),
            )
        await self.session.flush()
        if delivery.status == "failed":
            await emit_event(
                self.session, DomainEventType.CUSTOMER_PILOT_NOTIFICATION_FAILED,
                organization_id=delivery.organization_id,
                payload=sanitize_customer_view({"delivery_id": delivery.id}),
            )

    async def deliver_in_app(
        self,
        *,
        organization_id: str,
        user_id: str,
        title: str,
        body: str,
        action_url: str,
        idempotency_key: str,
        communication_id: str | None = None,
        approval_id: str | None = None,
        suppressed: bool = False,
    ) -> PilotNotificationDelivery:
        delivery = await self.get_or_create(
            organization_id=organization_id,
            recipient_user_id=user_id,
            channel="in_app",
            idempotency_key=idempotency_key,
            communication_id=communication_id,
            approval_id=approval_id,
        )
        if delivery.status in ("sent", "delivered", "suppressed_by_preference"):
            return delivery
        if suppressed:
            await self.mark_suppressed(delivery)
            return delivery
        try:
            self.session.add(InboxNotification(
                organization_id=organization_id,
                user_id=user_id,
                title=title[:300],
                body=body[:4000],
                category="customer_pilot",
                priority="normal",
                action_url=action_url,
                meta={"delivery_id": delivery.id},
            ))
            await self.mark_sent(delivery)
            delivery.status = "delivered"
            delivery.delivered_at = datetime.now(UTC)
            await self.session.flush()
            metrics.record_customer_pilot_notification_delivery("delivered")
        except Exception as exc:
            await self.mark_failed(delivery, str(exc))
        return delivery

    async def delivery_stats(self, organization_id: str | None = None) -> dict:
        stmt = select(
            PilotNotificationDelivery.status,
            func.count(),
        ).group_by(PilotNotificationDelivery.status)
        if organization_id:
            stmt = stmt.where(PilotNotificationDelivery.organization_id == organization_id)
        rows = (await self.session.execute(stmt)).all()
        counts = {status: count for status, count in rows}

        oldest = (await self.session.execute(
            select(func.min(PilotNotificationDelivery.queued_at)).where(
                PilotNotificationDelivery.status == "queued",
            ),
        )).scalar_one_or_none()

        oldest_seconds = None
        if oldest:
            ts = oldest if oldest.tzinfo else oldest.replace(tzinfo=UTC)
            oldest_seconds = (datetime.now(UTC) - ts).total_seconds()

        metrics.set_customer_pilot_notification_queue_oldest(oldest_seconds or 0)
        return {
            "counts_by_status": counts,
            "failed_count": counts.get("failed", 0),
            "retrying_count": counts.get("retrying", 0),
            "oldest_queued_seconds": oldest_seconds,
        }

    async def _requeue_rate_ok(self, organization_id: str) -> bool:
        cutoff = datetime.now(UTC) - _REQUEUE_WINDOW
        recent = (await self.session.execute(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.organization_id == organization_id,
                AuditLog.action == "pilot.notification_delivery_requeued",
                AuditLog.created_at >= cutoff,
            ),
        )).scalar_one()
        return int(recent or 0) < _REQUEUE_RATE_LIMIT

    async def requeue(
        self, user: User, organization_id: str, communication_id: str, delivery_id: str,
    ) -> dict:
        delivery = await self.session.get(PilotNotificationDelivery, delivery_id)
        if not delivery or delivery.organization_id != organization_id:
            raise NotFoundError("PilotNotificationDelivery", delivery_id)
        if delivery.communication_id != communication_id:
            raise ValidationError("Delivery does not belong to this communication")

        if delivery.status == "queued":
            return sanitize_customer_view({
                "delivery_id": delivery.id,
                "status": delivery.status,
                "requeued_at": delivery.queued_at.isoformat() if delivery.queued_at else None,
                "idempotent": True,
            })

        if delivery.status not in ("failed", "cancelled"):
            raise ValidationError("Only failed or cancelled deliveries can be requeued")

        if not await self._requeue_rate_ok(organization_id):
            raise ValidationError("Requeue rate limit exceeded for this organization")

        if delivery.approval_id:
            approval = await self.session.get(PilotApproval, delivery.approval_id)
            if not approval or approval.status != "PENDING":
                raise ValidationError("Cannot requeue reminder delivery for non-pending approval")

        delivery.status = "queued"
        delivery.attempts = 0
        delivery.next_retry_at = None
        delivery.last_error = None
        delivery.queued_at = datetime.now(UTC)
        await self.session.flush()

        await self.audit.log(
            action="pilot.notification_delivery_requeued",
            resource_type="pilot_notification_delivery",
            resource_id=delivery.id,
            user_id=user.id,
            organization_id=organization_id,
            details={"communication_id": communication_id},
        )
        await emit_event(
            self.session, DomainEventType.CUSTOMER_PILOT_NOTIFICATION_REQUEUED,
            organization_id=organization_id,
            actor_id=user.id,
            payload=sanitize_customer_view({"delivery_id": delivery.id}),
        )
        return sanitize_customer_view({
            "delivery_id": delivery.id,
            "status": delivery.status,
            "requeued_at": delivery.queued_at.isoformat(),
        })
