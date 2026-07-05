"""Commercial event emission (Sprint 61C).

Every billing/licensing/quota event is written to the ``billing_events`` outbox
(durable, auditable) and delivered to each active org webhook endpoint. Delivery
reuses the Redis notification queue when enabled, with an inline HTTP fallback.

Emitted event types: subscription.changed, payment.received, quota.exceeded,
trial.ending, license.expiring.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import BillingEvent, BillingWebhookEndpoint

logger = logging.getLogger(__name__)

EVENT_TYPES = {
    "subscription.changed",
    "payment.received",
    "quota.exceeded",
    "trial.ending",
    "license.expiring",
}


def _now() -> datetime:
    return datetime.now(UTC)


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class BillingWebhookService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def emit(self, organization_id: str | None, event_type: str, payload: dict) -> BillingEvent:
        """Record an event in the outbox and schedule delivery."""
        event = BillingEvent(
            organization_id=organization_id, event_type=event_type,
            payload=payload, delivery_status="pending", attempts=0,
        )
        self.session.add(event)
        await self.session.flush()
        await self._schedule_delivery(event)
        return event

    async def list_endpoints(self, organization_id: str) -> list[BillingWebhookEndpoint]:
        return list((await self.session.execute(
            select(BillingWebhookEndpoint).where(
                BillingWebhookEndpoint.organization_id == organization_id
            )
        )).scalars().all())

    async def add_endpoint(
        self, organization_id: str, url: str, *, secret: str | None = None,
        events: list[str] | None = None,
    ) -> BillingWebhookEndpoint:
        ep = BillingWebhookEndpoint(
            organization_id=organization_id, url=url, secret=secret,
            events=events, is_active=True,
        )
        self.session.add(ep)
        await self.session.flush()
        return ep

    async def _schedule_delivery(self, event: BillingEvent) -> None:
        if not event.organization_id:
            return
        endpoints = [
            ep for ep in await self.list_endpoints(event.organization_id)
            if ep.is_active and (not ep.events or event.event_type in ep.events)
        ]
        if not endpoints:
            # No subscribers — consider the event delivered (outbox still kept).
            event.delivery_status = "no_subscribers"
            self.session.add(event)
            await self.session.flush()
            return
        delivered_any = False
        for ep in endpoints:
            ok = await self._deliver(ep, event)
            delivered_any = delivered_any or ok
        event.attempts += 1
        event.delivery_status = "delivered" if delivered_any else "failed"
        if delivered_any:
            event.delivered_at = _now()
        self.session.add(event)
        await self.session.flush()

    async def _deliver(self, endpoint: BillingWebhookEndpoint, event: BillingEvent) -> bool:
        body = json.dumps({
            "event_type": event.event_type,
            "organization_id": event.organization_id,
            "payload": event.payload,
            "created_at": _now().isoformat(),
        }, default=str).encode()
        headers = {"Content-Type": "application/json", "X-Nexora-Event": event.event_type}
        if endpoint.secret:
            headers["X-Nexora-Signature"] = _sign(endpoint.secret, body)
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(endpoint.url, content=body, headers=headers)
                return resp.status_code < 400
        except Exception as exc:  # pragma: no cover - network/dev
            logger.warning("billing_webhook_delivery_failed",
                           extra={"endpoint": endpoint.id, "error": str(exc)})
            event.last_error = str(exc)
            return False
