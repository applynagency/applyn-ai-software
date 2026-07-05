"""Sprint 42A — IncidentNotificationService.

Notifies humans (Slack / Email) when the monitoring engine auto-creates an
incident. The notification is purely outbound and customer-safe: it carries the
incident id, severity, suspected cause, confidence, the top recommended action,
and a link to the incident — never secrets, credentials, or raw provider data.

Delivery is best-effort and degrades gracefully: when a Slack webhook is
configured it is POSTed; otherwise the send is recorded (and audited) so local /
dev / test environments work unchanged. Every send is audited. This service
never executes remediation or mutates infrastructure.
"""

from __future__ import annotations

import structlog

from app.core.config import settings
from app.repositories.audit import AuditLogRepository

logger = structlog.get_logger(__name__)


async def send_slack_text(text: str, *, webhook: str | None = None) -> None:
    """Deliver a customer-safe text line to Slack (or log in degraded mode)."""
    from app.core.config import settings

    target = webhook or settings.SLACK_WEBHOOK_URL
    if not target:
        logger.info("incident_notification_slack_simulated", text=text[:200])
        return
    import httpx

    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(target, json={"text": text})


async def send_teams_text(text: str, *, webhook: str | None = None) -> None:
    """Deliver a customer-safe text line to Microsoft Teams (or log in degraded mode)."""
    from app.core.config import settings

    target = webhook or settings.TEAMS_WEBHOOK_URL
    if not target:
        logger.info("incident_notification_teams_simulated", text=text[:200])
        return
    import httpx

    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(target, json={"text": text})


async def send_email_summary(severity: str, title: str) -> None:
    """Deliver an email summary (or log in degraded mode — no SMTP wired)."""
    logger.info(
        "incident_notification_email_simulated",
        subject=f"[{severity}] {title}"[:200],
    )


async def deliver_transport(payload: dict) -> bool:
    """Deliver a queued notification payload across its channels.

    Returns ``True`` when every requested channel was delivered (so the queue
    can drop it), ``False`` to trigger a retry.
    """
    channels = payload.get("channels") or ["slack", "email"]
    text = payload.get("text", "")
    severity = payload.get("severity", "INFO")
    title = payload.get("title", "")
    organization_id = payload.get("organization_id")
    webhooks = payload.get("webhooks") or {}
    ok = True
    for channel in channels:
        try:
            if channel == "slack":
                await send_slack_text(text, webhook=webhooks.get("slack"))
            elif channel == "teams":
                await send_teams_text(text, webhook=webhooks.get("teams"))
            elif channel == "pagerduty":
                routing_key = webhooks.get("pagerduty_routing_key")
                if routing_key:
                    from app.services.pagerduty_outbound import trigger_event
                    result = await trigger_event(
                        routing_key, summary=title or text[:200], severity=severity,
                        custom_details={"message": text[:500]},
                    )
                    if not result.get("sent"):
                        ok = False
            elif channel == "email":
                await send_email_summary(severity, title)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("notification_transport_failed", channel=channel, error=str(exc))
            ok = False
    return ok


class IncidentNotificationService:
    def __init__(self, session):
        self.session = session
        self.audit_repo = AuditLogRepository(session)

    def build_message(
        self,
        *,
        incident_id: str,
        title: str,
        severity: str,
        suspected_cause: str | None,
        confidence: int | None,
        recommended_action: str | None,
    ) -> dict:
        link = f"{settings.INCIDENT_LINK_BASE_URL}/incidents/{incident_id}"
        return {
            "incident_id": incident_id,
            "title": title,
            "severity": severity,
            "suspected_cause": suspected_cause or "Under investigation",
            "confidence": confidence if confidence is not None else 0,
            "recommended_action": recommended_action or "Review investigation findings",
            "link": link,
            "text": (
                f"[{severity}] Incident auto-created: {title}\n"
                f"Suspected cause: {suspected_cause or 'Under investigation'} "
                f"(confidence {confidence if confidence is not None else 0}%)\n"
                f"Recommended action: {recommended_action or 'Review findings'}\n"
                f"View: {link}"
            ),
        }

    async def notify_incident(
        self,
        *,
        organization_id: str,
        incident_id: str,
        title: str,
        severity: str,
        suspected_cause: str | None = None,
        confidence: int | None = None,
        recommended_action: str | None = None,
        channels: list[str] | None = None,
        user_id: str | None = None,
    ) -> list[str]:
        """Send a customer-safe incident notification. Returns delivered channels.

        Caller is responsible for committing the session (the audit row is only
        flushed here, mirroring the rest of the codebase)."""
        if not settings.NOTIFICATIONS_ENABLED:
            return []

        channels = channels or ["slack", "email"]
        message = self.build_message(
            incident_id=incident_id,
            title=title,
            severity=severity,
            suspected_cause=suspected_cause,
            confidence=confidence,
            recommended_action=recommended_action,
        )

        delivered = await self._dispatch(
            channels,
            text=message["text"],
            severity=severity,
            title=title,
            incident_id=incident_id,
            organization_id=organization_id,
        )

        await self.audit_repo.log(
            action="incident_notification_sent",
            resource_type="incident_investigation",
            resource_id=incident_id,
            user_id=user_id,
            details={
                "organization_id": organization_id,
                "severity": severity,
                "channels": delivered,
                "has_recommendation": bool(recommended_action),
            },
        )
        return delivered

    async def notify_recipient(
        self,
        *,
        organization_id: str,
        incident_id: str,
        title: str,
        severity: str,
        reason: str,
        recipient_user_id: str | None = None,
        recipient_label: str | None = None,
        channels: list[str] | None = None,
        user_id: str | None = None,
        suspected_cause: str | None = None,
        confidence: int | None = None,
        recommended_action: str | None = None,
    ) -> list[str]:
        """Notify a specific responder/owner (on-call assignment or escalation).

        ``reason`` is a customer-safe phrase like "on-call assignment" or
        "escalation level 2 (no acknowledgement after 20m)". Never logs secrets.
        Caller commits the session."""
        if not settings.NOTIFICATIONS_ENABLED:
            return []
        channels = channels or ["slack", "email"]
        link = f"{settings.INCIDENT_LINK_BASE_URL}/incidents/{incident_id}"
        who = recipient_label or (recipient_user_id or "responder")
        rca_line = ""
        if suspected_cause:
            rca_line = (
                f"\nSuspected cause: {suspected_cause}"
                f"{f' ({confidence}% confidence)' if confidence is not None else ''}"
            )
        fix_line = f"\nRecommended fix: {recommended_action}" if recommended_action else ""
        text = (
            f"[{severity}] {reason}: {title}\n"
            f"Assigned to: {who}\n"
            f"Action required: acknowledge the incident.{rca_line}{fix_line}\n"
            f"View: {link}"
        )
        delivered = await self._dispatch(
            channels,
            text=text,
            severity=severity,
            title=title,
            incident_id=incident_id,
            organization_id=organization_id,
        )
        await self.audit_repo.log(
            action="incident_notification_sent",
            resource_type="incident_investigation",
            resource_id=incident_id,
            user_id=user_id,
            details={
                "organization_id": organization_id,
                "severity": severity,
                "reason": reason,
                "channels": delivered,
                "recipient_user_id": recipient_user_id,
            },
        )
        return delivered

    async def _dispatch(
        self,
        channels: list[str],
        *,
        text: str,
        severity: str,
        title: str,
        incident_id: str,
        organization_id: str | None = None,
    ) -> list[str]:
        """Send inline, or buffer on the Redis notification queue when enabled.

        Returns the channels that were delivered (inline) or accepted (queued).
        """
        webhooks: dict = {}
        if organization_id and self.session is not None:
            from app.services.notification_channels import OrgNotificationChannelService

            svc = OrgNotificationChannelService(self.session)
            webhooks["slack"] = await svc.resolve_slack_webhook(organization_id)
            webhooks["teams"] = await svc.resolve_teams_webhook(organization_id)
            webhooks["pagerduty_routing_key"] = await svc.resolve_pagerduty_routing_key(organization_id)

        if settings.NOTIFICATION_QUEUE_ENABLED:
            from app.redis import notifications

            await notifications.enqueue(
                {
                    "channels": channels,
                    "text": text,
                    "severity": severity,
                    "title": title,
                    "incident_id": incident_id,
                    "organization_id": organization_id,
                    "webhooks": webhooks,
                }
            )
            return list(channels)

        delivered: list[str] = []
        for channel in channels:
            try:
                if channel == "slack":
                    await send_slack_text(text, webhook=webhooks.get("slack"))
                elif channel == "teams":
                    await send_teams_text(text, webhook=webhooks.get("teams"))
                elif channel == "pagerduty":
                    routing_key = webhooks.get("pagerduty_routing_key")
                    if routing_key:
                        from app.services.pagerduty_outbound import trigger_event
                        result = await trigger_event(
                            routing_key, summary=title or text[:200], severity=severity,
                            custom_details={"message": text[:500]},
                        )
                        if result.get("sent"):
                            delivered.append(channel)
                    continue
                elif channel == "email":
                    await send_email_summary(severity, title)
                delivered.append(channel)
            except Exception as exc:  # pragma: no cover - defensive, never leaks
                logger.warning(
                    "incident_notification_channel_failed",
                    channel=channel,
                    incident_id=incident_id,
                    error=str(exc),
                )
        return delivered
