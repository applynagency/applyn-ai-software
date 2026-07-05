"""Database-backed session management.

Each login creates a ``UserSession`` row bound to the SHA-256 of its refresh
token. Refreshing rotates the stored hash; presenting a superseded refresh token
(token reuse) revokes the whole session as a theft signal. Supports device
history, logout-one / logout-all, revocation and concurrent-session limits.
"""

from __future__ import annotations

import hashlib
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.base import utcnow
from app.models.identity import UserSession
from app.repositories.audit import AuditLogRepository


def hash_refresh(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SessionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditLogRepository(session)

    async def create(
        self,
        *,
        user_id: str,
        refresh_token: str,
        access_jti: str | None = None,
        organization_id: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
        max_concurrent: int = 0,
        ttl_days: int | None = None,
    ) -> UserSession:
        days = ttl_days if ttl_days is not None else settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        now = utcnow()
        sess = UserSession(
            user_id=user_id,
            organization_id=organization_id,
            refresh_token_hash=hash_refresh(refresh_token),
            access_jti=access_jti,
            ip_address=(ip or None) and ip[:45],
            user_agent=user_agent,
            device_label=_device_label(user_agent),
            last_seen_at=now,
            expires_at=now + timedelta(days=days),
        )
        self.session.add(sess)
        await self.session.flush()

        if max_concurrent and max_concurrent > 0:
            await self._enforce_concurrency(user_id, max_concurrent, keep_id=sess.id)

        await self.audit.log(
            action="session.created",
            resource_type="session",
            resource_id=sess.id,
            user_id=user_id,
            organization_id=organization_id,
            details={"ip": sess.ip_address, "device": sess.device_label},
        )
        return sess

    async def _active_query(self, user_id: str):
        return select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > utcnow(),
        )

    async def list_active(self, user_id: str) -> list[UserSession]:
        stmt = (await self._active_query(user_id)).order_by(
            UserSession.last_seen_at.desc()
        )
        return list((await self.session.scalars(stmt)).all())

    async def _enforce_concurrency(
        self, user_id: str, max_concurrent: int, *, keep_id: str
    ) -> None:
        active = await self.list_active(user_id)
        if len(active) <= max_concurrent:
            return
        # Revoke the oldest sessions beyond the limit (keep newest, incl. keep_id).
        active.sort(key=lambda s: s.last_seen_at or s.created_at, reverse=True)
        for sess in active[max_concurrent:]:
            if sess.id == keep_id:
                continue
            sess.revoked_at = utcnow()
            sess.revoked_reason = "concurrent_limit"
            self.session.add(sess)
        await self.session.flush()

    async def rotate(
        self,
        *,
        old_refresh_token: str,
        new_refresh_token: str,
        access_jti: str | None = None,
        ip: str | None = None,
    ) -> UserSession | None:
        """Rotate a session's refresh token. Returns the session, or None if the
        presented token does not match any active session.

        If the token matches a *revoked* session (reuse), nothing is rotated.
        """
        old_hash = hash_refresh(old_refresh_token)
        sess = await self.session.scalar(
            select(UserSession).where(UserSession.refresh_token_hash == old_hash)
        )
        if sess is None:
            return None
        if sess.revoked_at is not None or (
            sess.expires_at is not None and sess.expires_at <= utcnow()
        ):
            return None
        sess.refresh_token_hash = hash_refresh(new_refresh_token)
        sess.access_jti = access_jti
        sess.rotation_count += 1
        sess.last_seen_at = utcnow()
        if ip:
            sess.ip_address = ip[:45]
        self.session.add(sess)
        await self.session.flush()
        return sess

    async def get(self, session_id: str) -> UserSession | None:
        return await self.session.get(UserSession, session_id)

    async def revoke(
        self,
        *,
        user_id: str,
        session_id: str,
        reason: str = "user_logout",
    ) -> bool:
        sess = await self.session.get(UserSession, session_id)
        if sess is None or sess.user_id != user_id or sess.revoked_at is not None:
            return False
        sess.revoked_at = utcnow()
        sess.revoked_reason = reason
        self.session.add(sess)
        await self.session.flush()
        await self.audit.log(
            action="session.revoked",
            resource_type="session",
            resource_id=sess.id,
            user_id=user_id,
            organization_id=sess.organization_id,
            details={"reason": reason},
        )
        return True

    async def revoke_all(
        self, *, user_id: str, keep_session_id: str | None = None, reason: str = "logout_all"
    ) -> int:
        active = await self.list_active(user_id)
        revoked = 0
        for sess in active:
            if keep_session_id and sess.id == keep_session_id:
                continue
            sess.revoked_at = utcnow()
            sess.revoked_reason = reason
            self.session.add(sess)
            revoked += 1
        if revoked:
            await self.session.flush()
            await self.audit.log(
                action="session.revoked_all",
                resource_type="session",
                resource_id=user_id,
                user_id=user_id,
                details={"revoked": revoked, "reason": reason},
            )
        return revoked


def _device_label(user_agent: str | None) -> str | None:
    if not user_agent:
        return None
    ua = user_agent.lower()
    os_name = next(
        (n for k, n in (
            ("windows", "Windows"), ("mac os", "macOS"), ("iphone", "iOS"),
            ("ipad", "iPadOS"), ("android", "Android"), ("linux", "Linux"),
        ) if k in ua),
        "Unknown OS",
    )
    browser = next(
        (n for k, n in (
            ("edg", "Edge"), ("chrome", "Chrome"), ("firefox", "Firefox"),
            ("safari", "Safari"),
        ) if k in ua),
        "Unknown browser",
    )
    return f"{browser} on {os_name}"
