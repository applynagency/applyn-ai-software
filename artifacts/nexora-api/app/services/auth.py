import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.token_service import issue_tokens
from app.core.config import settings
from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.logging import get_logger
from app.core.security import (
    decode_token,
    hash_password,
    token_remaining_seconds,
    verify_password,
    verify_token,
)
from app.models.organization import OrganizationRole
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.organization import OrganizationMemberRepository
from app.repositories.user import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse

logger = get_logger(__name__)


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.audit_repo = AuditLogRepository(session)

    async def register(self, data: RegisterRequest, ip: str = "") -> UserResponse:
        existing_email = await self.user_repo.get_by_email(data.email)
        if existing_email:
            raise ConflictError("Email is already registered")

        existing_username = await self.user_repo.get_by_username(data.username)
        if existing_username:
            raise ConflictError("Username is already taken")

        user = await self.user_repo.create(
            email=data.email,
            username=data.username,
            full_name=data.full_name,
            hashed_password=hash_password(data.password),
        )

        await self.audit_repo.log(
            action="user.register",
            resource_type="user",
            resource_id=user.id,
            user_id=user.id,
            details={"email": user.email},
            ip_address=ip,
        )

        logger.info("user_registered", user_id=user.id, email=user.email)
        return UserResponse.model_validate(user)

    async def login(
        self, data: LoginRequest, ip: str = "", user_agent: str | None = None
    ) -> TokenResponse:
        from app.services.identity.anomaly import LoginAnomalyDetector

        anomaly = LoginAnomalyDetector(self.session)
        user = await self.user_repo.get_by_email(data.email)

        # Brute-force lockout: too many recent failures short-circuits even a
        # correct password (opt-in; threshold 0 disables, audit-only).
        if await anomaly.is_locked(
            user_id=getattr(user, "id", None), email=data.email
        ):
            raise UnauthorizedError("Account temporarily locked due to repeated failures")

        # SSO-only users have no local password (hashed_password is NULL) and
        # must authenticate through their identity provider.
        if (
            not user
            or not user.hashed_password
            or not verify_password(data.password, user.hashed_password)
        ):
            await anomaly.record_failure(
                email=data.email, ip=ip, user_id=getattr(user, "id", None))
            raise UnauthorizedError("Invalid email or password")

        if not user.is_active:
            raise UnauthorizedError("Account is deactivated")

        # Second factor: enforce MFA for any account that has it enabled.
        from app.services.identity.mfa import MfaService

        mfa = MfaService(self.session)
        if await mfa.is_enrolled(user.id):
            if not data.mfa_code:
                raise UnauthorizedError("MFA code required")
            if not await mfa.verify(user.id, data.mfa_code):
                raise UnauthorizedError("Invalid MFA code")

        tokens = await issue_tokens(self.session, user.id)
        await self._register_session(tokens, user_id=user.id, ip=ip, user_agent=user_agent)
        await self._register_db_session(
            tokens, user_id=user.id, ip=ip, user_agent=user_agent
        )

        await self.audit_repo.log(
            action="user.login",
            resource_type="user",
            resource_id=user.id,
            user_id=user.id,
            ip_address=ip,
        )

        # Suspicious-login detection: flag logins from a new IP/device.
        await anomaly.check_login(user_id=user.id, ip=ip, user_agent=user_agent)

        logger.info("user_login", user_id=user.id)
        return tokens

    async def _register_db_session(
        self,
        tokens: TokenResponse,
        *,
        user_id: str,
        ip: str = "",
        user_agent: str | None = None,
    ) -> None:
        """Record a database-backed session (device history + refresh rotation)."""
        if not settings.DB_SESSIONS_ENABLED:
            return
        try:
            payload = decode_token(tokens.access_token)
            max_concurrent = 0
            if tokens.organization_id:
                from app.services.identity.security_policy import SecurityPolicyService

                policy = await SecurityPolicyService(self.session).get(
                    tokens.organization_id
                )
                if policy:
                    max_concurrent = policy.max_concurrent_sessions
            from app.services.identity.sessions import SessionService

            await SessionService(self.session).create(
                user_id=user_id,
                refresh_token=tokens.refresh_token,
                access_jti=payload.get("jti"),
                organization_id=tokens.organization_id,
                ip=ip or None,
                user_agent=user_agent,
                max_concurrent=max_concurrent,
            )
        except Exception as exc:  # pragma: no cover - never block login
            logger.warning("db_session_register_failed", error=str(exc))

    async def _register_session(
        self,
        tokens: TokenResponse,
        *,
        user_id: str,
        ip: str = "",
        user_agent: str | None = None,
    ) -> None:
        """Best-effort: record an active server-side session for the new token."""
        if not settings.SESSION_STORE_ENABLED:
            return
        try:
            payload = decode_token(tokens.access_token)
            jti = payload.get("jti")
            if not jti:
                return
            from app.redis import sessions

            await sessions.create(
                jti=jti,
                user_id=user_id,
                ttl_seconds=token_remaining_seconds(payload),
                ip=ip or None,
                user_agent=user_agent,
                organization_id=payload.get("organization_id"),
            )
        except Exception as exc:  # pragma: no cover - never block login
            logger.warning("session_register_failed", error=str(exc))

    async def refresh(
        self, refresh_token: str, organization_id: str | None = None
    ) -> TokenResponse:
        user_id = verify_token(refresh_token, token_type="refresh")
        if not user_id:
            raise UnauthorizedError("Invalid or expired refresh token")

        user = await self.user_repo.get_by_id(user_id)
        if not user or user.refresh_token != refresh_token:
            raise UnauthorizedError("Refresh token has been revoked")

        resolved_org_id = organization_id
        if not resolved_org_id:
            try:
                payload = decode_token(refresh_token)
                token_org_id = payload.get("organization_id")
                if token_org_id:
                    resolved_org_id = str(token_org_id)
            except Exception:
                resolved_org_id = None

        resolved_role: OrganizationRole | None = None
        if resolved_org_id:
            member_repo = OrganizationMemberRepository(self.session)
            membership = await member_repo.get_membership(resolved_org_id, user.id)
            if membership:
                resolved_role = membership.role
            elif user.is_superuser:
                resolved_role = OrganizationRole.OWNER
            else:
                resolved_org_id = None

        tokens = await issue_tokens(
            self.session,
            user.id,
            organization_id=resolved_org_id,
            role=resolved_role,
        )
        await self._rotate_db_session(refresh_token, tokens)
        return tokens

    async def _rotate_db_session(
        self, old_refresh_token: str, tokens: TokenResponse
    ) -> None:
        """Rotate the database session's refresh token (reuse → no rotation)."""
        if not settings.DB_SESSIONS_ENABLED:
            return
        try:
            payload = decode_token(tokens.access_token)
            from app.services.identity.sessions import SessionService

            await SessionService(self.session).rotate(
                old_refresh_token=old_refresh_token,
                new_refresh_token=tokens.refresh_token,
                access_jti=payload.get("jti"),
            )
        except Exception as exc:  # pragma: no cover - never block refresh
            logger.warning("db_session_rotate_failed", error=str(exc))

    async def logout(self, user: User, access_payload: dict | None = None) -> None:
        # Revoke the presented access token (denylist + drop its session) so it
        # cannot be reused before its natural expiry, then clear the stored
        # refresh token.
        if access_payload:
            await self._revoke_token(access_payload)
            await self._revoke_db_session_by_jti(user, access_payload.get("jti"))
        await self.user_repo.update_refresh_token(user, None)
        await self.audit_repo.log(
            action="user.logout",
            resource_type="user",
            resource_id=user.id,
            user_id=user.id,
        )
        logger.info("user_logout", user_id=user.id)

    async def _revoke_db_session_by_jti(self, user: User, jti: str | None) -> None:
        if not settings.DB_SESSIONS_ENABLED or not jti:
            return
        try:
            from app.services.identity.sessions import SessionService

            svc = SessionService(self.session)
            for sess in await svc.list_active(user.id):
                if sess.access_jti == jti:
                    await svc.revoke(
                        user_id=user.id, session_id=sess.id, reason="user_logout"
                    )
                    break
        except Exception as exc:  # pragma: no cover - never block logout
            logger.warning("db_session_revoke_failed", error=str(exc))

    async def _revoke_token(self, payload: dict) -> None:
        jti = payload.get("jti")
        if not jti:
            return
        if settings.JWT_DENYLIST_ENABLED:
            from app.redis import denylist

            await denylist.revoke(jti, token_remaining_seconds(payload))
        if settings.SESSION_STORE_ENABLED:
            from app.redis import sessions

            await sessions.delete(jti)

    async def list_sessions(self, user: User) -> list[dict]:
        from app.redis import sessions

        return await sessions.list_for_user(user.id)

    async def revoke_session(self, user: User, jti: str) -> bool:
        """Revoke one of the user's own sessions by jti."""
        from app.redis import denylist, sessions

        meta = await sessions.get(jti)
        if not meta or meta.get("user_id") != user.id:
            return False
        if settings.JWT_DENYLIST_ENABLED:
            ttl = max(1, int(meta.get("expires_at", 0) - time.time()))
            await denylist.revoke(jti, ttl)
        await sessions.delete(jti)
        await self.audit_repo.log(
            action="user.session_revoked",
            resource_type="user",
            resource_id=user.id,
            user_id=user.id,
            details={"jti": jti},
        )
        return True

    async def revoke_other_sessions(self, user: User, current_jti: str | None) -> int:
        """Revoke every session for the user except the current one."""
        from app.redis import denylist, sessions

        active = await sessions.list_for_user(user.id)
        revoked = 0
        for meta in active:
            jti = meta["jti"]
            if current_jti and jti == current_jti:
                continue
            if settings.JWT_DENYLIST_ENABLED:
                ttl = max(1, int(meta.get("expires_at", 0) - time.time()))
                await denylist.revoke(jti, ttl)
            await sessions.delete(jti)
            revoked += 1
        if revoked:
            await self.audit_repo.log(
                action="user.sessions_revoked_all",
                resource_type="user",
                resource_id=user.id,
                user_id=user.id,
                details={"revoked": revoked},
            )
        return revoked
