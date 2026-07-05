"""Login + session anomaly detection (Sprint 62B).

Adds the signals enterprise security teams expect on top of the existing rate
limiter and audit trail:

* failed-login auditing + per-account counting (brute-force visibility)
* suspicious-login detection — a successful login from a never-before-seen IP or
  device for that user raises a tamper-evident ``user.login_suspicious`` audit
  event (and a domain event for downstream notification)

Best-effort: detection must never block a legitimate login, so every method
swallows its own errors. Backed entirely by data already captured
(``UserSession`` device/IP history + audit logs).
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.database.base import utcnow

logger = get_logger(__name__)


class LoginAnomalyDetector:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_failure(self, *, email: str, ip: str = "",
                             user_id: str | None = None) -> int:
        """Audit a failed login and return recent failure count for the account."""
        from app.repositories.audit import AuditLogRepository

        try:
            await AuditLogRepository(self.session).log(
                action="user.login_failed",
                resource_type="user",
                resource_id=user_id or email,
                user_id=user_id,
                details={"email": email[:255]},
                ip_address=ip,
            )
        except Exception as exc:  # noqa: BLE001 - never block the auth path
            logger.warning("login_failure_audit_failed", error=str(exc))
        return await self.recent_failures(user_id=user_id, email=email)

    async def recent_failures(self, *, user_id: str | None = None,
                              email: str | None = None, minutes: int = 15) -> int:
        from app.models.audit import AuditLog

        since = utcnow() - timedelta(minutes=minutes)
        stmt = select(func.count(AuditLog.id)).where(
            AuditLog.action == "user.login_failed",
            AuditLog.created_at >= since,
        )
        if user_id:
            stmt = stmt.where(AuditLog.user_id == user_id)
        elif email:
            stmt = stmt.where(AuditLog.resource_id == email)
        return int((await self.session.execute(stmt)).scalar() or 0)

    async def is_locked(self, *, user_id: str | None, email: str) -> bool:
        threshold = int(getattr(settings, "LOGIN_FAILURE_LOCK_THRESHOLD", 0) or 0)
        if threshold <= 0:
            return False
        return await self.recent_failures(user_id=user_id, email=email) >= threshold

    async def check_login(self, *, user_id: str, ip: str = "",
                          user_agent: str | None = None,
                          organization_id: str | None = None) -> dict | None:
        """Flag a successful login from a new IP/device. Returns the anomaly dict."""
        if not getattr(settings, "LOGIN_ANOMALY_DETECTION_ENABLED", True):
            return None
        try:
            from app.models.identity import UserSession
            from app.services.identity.sessions import _device_label

            device = _device_label(user_agent) if user_agent else None
            # Compare against this user's historical sessions.
            rows = (await self.session.execute(
                select(UserSession.ip_address, UserSession.device_label).where(
                    UserSession.user_id == user_id).limit(200))).all()
            if not rows:
                return None  # first login — nothing to compare against
            known_ips = {r[0] for r in rows if r[0]}
            known_devices = {r[1] for r in rows if r[1]}
            reasons = []
            if ip and known_ips and ip not in known_ips:
                reasons.append("new_ip")
            if device and known_devices and device not in known_devices:
                reasons.append("new_device")
            if not reasons:
                return None

            anomaly = {"user_id": user_id, "ip": ip, "device": device, "reasons": reasons}
            from app.repositories.audit import AuditLogRepository

            await AuditLogRepository(self.session).log(
                action="user.login_suspicious",
                resource_type="user",
                resource_id=user_id,
                user_id=user_id,
                details={"reasons": reasons, "device": device},
                ip_address=ip,
            )
            try:
                from app.platform.events import DomainEventType, emit_event

                await emit_event(
                    self.session, DomainEventType.NOTIFICATION_SENT,
                    organization_id=organization_id, actor_id=user_id,
                    aggregate_type="user", aggregate_id=user_id,
                    payload={"summary": "Suspicious login detected", **anomaly},
                    source="security")
            except Exception:  # noqa: BLE001 - notification is best-effort
                pass
            logger.info("login_anomaly_detected", user_id=user_id, reasons=reasons)
            return anomaly
        except Exception as exc:  # noqa: BLE001 - detection must not break login
            logger.warning("login_anomaly_check_failed", error=str(exc))
            return None
