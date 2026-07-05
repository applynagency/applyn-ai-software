"""Unified notification platform (Sprint 62A).

ONE notification service for the whole platform. Replaces scattered Slack/email
senders. Supports a pluggable channel-provider abstraction (email, Slack, Teams,
Discord, generic webhook, SMS, push), templates with localization, automatic
retries, and per-message delivery tracking.

Every channel degrades to a deterministic, network-free ``simulated`` delivery
when not configured, so the platform is fully usable (and testable) offline.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.database.base import utcnow
from app.models.platform_core import NotificationMessage, NotificationTemplate

logger = get_logger(__name__)


@dataclass
class DeliveryResult:
    ok: bool
    provider: str
    provider_message_id: str | None = None
    error: str | None = None


# --------------------------------------------------------------------------- #
# Channel providers
# --------------------------------------------------------------------------- #
class ChannelProvider:
    name = "base"

    def is_configured(self) -> bool:  # pragma: no cover - overridden
        return False

    async def send(self, message: NotificationMessage) -> DeliveryResult:
        raise NotImplementedError

    def _simulated(self, message: NotificationMessage) -> DeliveryResult:
        logger.info("notification_simulated", channel=self.name,
                    recipient=message.recipient, template=message.template_key)
        return DeliveryResult(ok=True, provider="simulated",
                              provider_message_id=f"sim-{message.id}")


async def _post_webhook(url: str, payload: dict) -> DeliveryResult:
    import httpx

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
    return DeliveryResult(ok=True, provider="webhook")


class EmailProvider(ChannelProvider):
    name = "email"

    def is_configured(self) -> bool:
        return bool(getattr(settings, "SMTP_HOST", "") or "")

    async def send(self, message: NotificationMessage) -> DeliveryResult:
        if not self.is_configured():
            return self._simulated(message)
        # Real SMTP send (kept dependency-light; uses stdlib smtplib in a thread).
        import asyncio
        import smtplib
        from email.message import EmailMessage

        def _send() -> None:
            msg = EmailMessage()
            msg["From"] = getattr(settings, "NOTIFICATION_EMAIL_FROM", "no-reply@nexora.local")
            msg["To"] = message.recipient
            msg["Subject"] = message.subject or "Notification"
            msg.set_content(message.body or "")
            host = settings.SMTP_HOST
            port = int(getattr(settings, "SMTP_PORT", 587) or 587)
            with smtplib.SMTP(host, port, timeout=10) as server:
                if getattr(settings, "SMTP_USE_TLS", True):
                    server.starttls()
                user = getattr(settings, "SMTP_USERNAME", "") or ""
                pwd = getattr(settings, "SMTP_PASSWORD", "") or ""
                if user:
                    server.login(user, pwd)
                server.send_message(msg)

        await asyncio.to_thread(_send)
        return DeliveryResult(ok=True, provider="smtp")


class _WebhookChannel(ChannelProvider):
    setting_name = ""

    def _url(self) -> str:
        return getattr(settings, self.setting_name, "") or ""

    def is_configured(self) -> bool:
        return bool(self._url())

    async def send(self, message: NotificationMessage) -> DeliveryResult:
        url = self._url()
        if not url:
            return self._simulated(message)
        return await _post_webhook(url, self._payload(message))

    def _payload(self, message: NotificationMessage) -> dict:
        text = message.body or message.subject or ""
        return {"text": text}


class SlackProvider(_WebhookChannel):
    name = "slack"
    setting_name = "SLACK_WEBHOOK_URL"


class TeamsProvider(_WebhookChannel):
    name = "teams"
    setting_name = "TEAMS_WEBHOOK_URL"

    def _payload(self, message: NotificationMessage) -> dict:
        return {"text": message.body or message.subject or ""}


class DiscordProvider(_WebhookChannel):
    name = "discord"
    setting_name = "DISCORD_WEBHOOK_URL"

    def _payload(self, message: NotificationMessage) -> dict:
        return {"content": message.body or message.subject or ""}


class WebhookProvider(ChannelProvider):
    name = "webhook"

    def is_configured(self) -> bool:
        return True  # recipient itself is the URL

    async def send(self, message: NotificationMessage) -> DeliveryResult:
        recipient = (message.recipient or "").strip()
        if not recipient.startswith("http"):
            return self._simulated(message)
        return await _post_webhook(recipient, {
            "subject": message.subject, "body": message.body,
            "payload": message.payload or {}})


class SMSProvider(ChannelProvider):
    name = "sms"

    def is_configured(self) -> bool:
        return bool(getattr(settings, "SMS_PROVIDER_URL", "") or "")

    async def send(self, message: NotificationMessage) -> DeliveryResult:
        url = getattr(settings, "SMS_PROVIDER_URL", "") or ""
        if not url:
            return self._simulated(message)
        return await _post_webhook(url, {"to": message.recipient, "body": message.body})


class PushProvider(ChannelProvider):
    name = "push"

    def is_configured(self) -> bool:
        return False  # future-ready; simulated for now

    async def send(self, message: NotificationMessage) -> DeliveryResult:
        return self._simulated(message)


_PROVIDERS: dict[str, ChannelProvider] = {
    p.name: p for p in (
        EmailProvider(), SlackProvider(), TeamsProvider(), DiscordProvider(),
        WebhookProvider(), SMSProvider(), PushProvider(),
    )
}

SUPPORTED_CHANNELS = tuple(_PROVIDERS.keys())


def get_provider(channel: str) -> ChannelProvider:
    if channel not in _PROVIDERS:
        raise KeyError(f"Unsupported notification channel: {channel}")
    return _PROVIDERS[channel]


# --------------------------------------------------------------------------- #
# Template rendering
# --------------------------------------------------------------------------- #
def _render(template: str | None, context: dict) -> str:
    if not template:
        return ""
    out = template
    for k, v in (context or {}).items():
        out = out.replace("{{" + str(k) + "}}", str(v))
    return out


# --------------------------------------------------------------------------- #
# Notification service
# --------------------------------------------------------------------------- #
class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_template(
        self,
        *,
        key: str,
        channel: str,
        body_template: str,
        subject_template: str | None = None,
        locale: str = "en",
        organization_id: str | None = None,
        created_by: str | None = None,
    ) -> NotificationTemplate:
        existing = (await self.session.execute(
            select(NotificationTemplate).where(
                NotificationTemplate.organization_id == organization_id,
                NotificationTemplate.key == key,
                NotificationTemplate.channel == channel,
                NotificationTemplate.locale == locale,
            ))).scalar_one_or_none()
        if existing:
            existing.body_template = body_template
            existing.subject_template = subject_template
            existing.is_active = True
        else:
            existing = NotificationTemplate(
                organization_id=organization_id, key=key, channel=channel,
                locale=locale, body_template=body_template,
                subject_template=subject_template, created_by=created_by)
            self.session.add(existing)
        await self.session.flush()
        return existing

    async def _resolve_template(
        self, key: str, channel: str, locale: str, organization_id: str | None,
    ) -> NotificationTemplate | None:
        # Resolution: org+locale → org+en → global+locale → global+en.
        candidates = [
            (organization_id, locale), (organization_id, "en"),
            (None, locale), (None, "en"),
        ]
        seen = set()
        for org, loc in candidates:
            sig = (org, loc)
            if sig in seen:
                continue
            seen.add(sig)
            tmpl = (await self.session.execute(
                select(NotificationTemplate).where(
                    NotificationTemplate.organization_id == org,
                    NotificationTemplate.key == key,
                    NotificationTemplate.channel == channel,
                    NotificationTemplate.locale == loc,
                    NotificationTemplate.is_active.is_(True),
                ))).scalar_one_or_none()
            if tmpl:
                return tmpl
        return None

    async def send(
        self,
        *,
        channel: str,
        recipient: str,
        organization_id: str | None = None,
        template_key: str | None = None,
        locale: str = "en",
        context: dict | None = None,
        subject: str | None = None,
        body: str | None = None,
        max_attempts: int = 4,
    ) -> NotificationMessage:
        if channel not in _PROVIDERS:
            raise KeyError(f"Unsupported notification channel: {channel}")
        context = context or {}

        if template_key:
            tmpl = await self._resolve_template(template_key, channel, locale, organization_id)
            if tmpl:
                subject = _render(tmpl.subject_template, context) or subject
                body = _render(tmpl.body_template, context)
                locale = tmpl.locale
        if body is None:
            body = str(context.get("body", "")) if context else ""

        message = NotificationMessage(
            organization_id=organization_id, channel=channel, recipient=recipient,
            template_key=template_key, locale=locale, subject=subject, body=body or "",
            payload=context, status="pending", max_attempts=max_attempts)
        self.session.add(message)
        await self.session.flush()

        await self._attempt(message)
        return message

    async def _attempt(self, message: NotificationMessage) -> NotificationMessage:
        provider = _PROVIDERS[message.channel]
        last_error: str | None = None
        while message.attempts < message.max_attempts:
            message.attempts += 1
            try:
                result = await provider.send(message)
            except Exception as exc:  # noqa: BLE001 - capture + retry
                last_error = str(exc)
                logger.warning("notification_attempt_failed", channel=message.channel,
                               attempt=message.attempts, error=last_error)
                continue
            if result.ok:
                message.status = "sent"
                message.provider = result.provider
                message.provider_message_id = result.provider_message_id
                message.error = None
                message.sent_at = utcnow()
                await self.session.flush()
                return message
            last_error = result.error
        message.error = last_error or "delivery failed"
        message.status = "dead_letter" if message.attempts >= message.max_attempts else "failed"
        await self.session.flush()
        return message

    async def retry(self, message_id: str) -> NotificationMessage | None:
        message = await self.session.get(NotificationMessage, message_id)
        if message is None or message.status == "sent":
            return message
        if message.attempts >= message.max_attempts:
            message.max_attempts += 1  # grant one more attempt on explicit retry
        return await self._attempt(message)

    async def list_messages(
        self, *, organization_id: str | None = None, status: str | None = None,
        channel: str | None = None, limit: int = 50, offset: int = 0,
    ) -> list[NotificationMessage]:
        stmt = select(NotificationMessage)
        if organization_id is not None:
            stmt = stmt.where(NotificationMessage.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(NotificationMessage.status == status)
        if channel is not None:
            stmt = stmt.where(NotificationMessage.channel == channel)
        stmt = stmt.order_by(NotificationMessage.created_at.desc()).limit(limit).offset(offset)
        return list((await self.session.execute(stmt)).scalars().all())
