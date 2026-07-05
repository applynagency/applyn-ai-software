"""SSO provisioning: role mapping, JIT user creation, org mapping, token issue.

Given normalized :class:`SSOClaims` from any provider, this service resolves the
local user (linking by external subject, then by email, then JIT-provisioning),
maps IdP groups to an organization role, maps the login to an organization, and
issues Nexora access/refresh tokens — mirroring the password login flow
(session registration + audit).
"""

from __future__ import annotations

import re

import structlog

from app.auth.token_service import issue_tokens
from app.core.config import settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token, token_remaining_seconds
from app.models.organization import OrganizationRole
from app.models.sso import SSOConnection
from app.repositories.audit import AuditLogRepository
from app.repositories.organization import (
    OrganizationMemberRepository,
    OrganizationRepository,
)
from app.repositories.sso import SSOIdentityRepository
from app.repositories.user import UserRepository
from app.schemas.auth import TokenResponse
from app.services.sso.claims import SSOClaims
from app.tenancy.backfill import ensure_user_has_organization

logger = structlog.get_logger(__name__)

# Higher index = more privilege; used to pick the strongest matching role.
_ROLE_PRIORITY = [
    OrganizationRole.VIEWER,
    OrganizationRole.DEVELOPER,
    OrganizationRole.PROJECT_MANAGER,
    OrganizationRole.ADMIN,
    OrganizationRole.OWNER,
]


def _coerce_role(value: str | None) -> OrganizationRole | None:
    if not value:
        return None
    try:
        return OrganizationRole(str(value).upper())
    except ValueError:
        return None


class SSOProvisioningService:
    def __init__(self, session):
        self.session = session
        self.user_repo = UserRepository(session)
        self.member_repo = OrganizationMemberRepository(session)
        self.org_repo = OrganizationRepository(session)
        self.identity_repo = SSOIdentityRepository(session)
        self.audit_repo = AuditLogRepository(session)

    async def provision_and_issue(
        self,
        connection: SSOConnection,
        claims: SSOClaims,
        *,
        ip: str = "",
        user_agent: str | None = None,
    ) -> TokenResponse:
        if not connection.enabled:
            raise UnauthorizedError("SSO connection is disabled")
        if not claims.email:
            raise UnauthorizedError("Identity provider did not return an email")
        self._enforce_domain(connection, claims)

        user, created = await self._resolve_user(connection, claims)
        await self._link_identity(connection, claims, user.id)

        role = self.resolve_role(connection, claims.groups)
        org_id = await self._resolve_organization(connection, claims, user)
        await self._ensure_membership(org_id, user.id, role)

        tokens = await issue_tokens(
            self.session, user.id, organization_id=org_id, role=role
        )
        await self._register_session(tokens, user_id=user.id, ip=ip, user_agent=user_agent)

        await self.audit_repo.log(
            action="sso.login",
            resource_type="sso_connection",
            resource_id=connection.id,
            user_id=user.id,
            details={
                "provider": connection.provider,
                "protocol": connection.protocol,
                "organization_id": org_id,
                "role": role.value,
                "jit_provisioned": created,
                "groups": claims.groups[:50],
            },
            ip_address=ip or None,
        )
        logger.info(
            "sso_login",
            connection=connection.slug,
            user_id=user.id,
            organization_id=org_id,
            role=role.value,
            jit=created,
        )
        return tokens

    # --- domain / role / org resolution -------------------------------------

    def _enforce_domain(self, connection: SSOConnection, claims: SSOClaims) -> None:
        allowed = [d.lower().lstrip("@") for d in (connection.allowed_email_domains or [])]
        if allowed and claims.email_domain not in allowed:
            raise ForbiddenError(
                f"Email domain '{claims.email_domain}' is not permitted for this connection"
            )

    def resolve_role(
        self, connection: SSOConnection, groups: list[str]
    ) -> OrganizationRole:
        """Map IdP groups to the strongest matching org role.

        Falls back to the connection's ``default_role`` then the global default.
        """
        mappings = {k.lower(): v for k, v in (connection.role_mappings or {}).items()}
        matched: list[OrganizationRole] = []
        for group in groups:
            mapped = _coerce_role(mappings.get(str(group).lower()))
            if mapped:
                matched.append(mapped)
        if matched:
            return max(matched, key=_ROLE_PRIORITY.index)
        return (
            _coerce_role(connection.default_role)
            or _coerce_role(settings.SSO_DEFAULT_ROLE)
            or OrganizationRole.VIEWER
        )

    async def _resolve_organization(
        self, connection: SSOConnection, claims: SSOClaims, user
    ) -> str:
        # 1) Connection scoped to a single org.
        if connection.organization_id:
            return connection.organization_id

        # 2) Tenant-wide: map by group or email domain to an org slug.
        mappings = {k.lower(): v for k, v in (connection.organization_mappings or {}).items()}
        candidates = [g.lower() for g in claims.groups] + [claims.email_domain]
        for key in candidates:
            slug = mappings.get(key)
            if slug:
                org = await self.org_repo.get_by_slug(str(slug))
                if org:
                    return org.id

        # 3) Fall back to the user's primary org (creating a default if needed).
        membership = await ensure_user_has_organization(self.session, user)
        return membership.organization_id

    async def _ensure_membership(
        self, org_id: str, user_id: str, role: OrganizationRole
    ) -> None:
        membership = await self.member_repo.get_membership(org_id, user_id)
        if membership is None:
            await self.member_repo.create(
                organization_id=org_id, user_id=user_id, role=role
            )
        elif membership.role != role:
            # Keep org role in sync with the IdP on every login.
            await self.member_repo.update(membership, role=role)

    # --- user resolution ----------------------------------------------------

    async def _resolve_user(self, connection: SSOConnection, claims: SSOClaims):
        identity = await self.identity_repo.get_by_subject(connection.id, claims.subject)
        if identity:
            user = await self.user_repo.get_by_id(identity.user_id)
            if user and user.is_active:
                return user, False
            if user and not user.is_active:
                raise UnauthorizedError("Account is deactivated")

        existing = await self.user_repo.get_by_email(claims.email.lower())
        if existing:
            if not existing.is_active:
                raise UnauthorizedError("Account is deactivated")
            return existing, False

        if not connection.auto_provision:
            raise ForbiddenError(
                "No matching account and automatic provisioning is disabled"
            )
        user = await self._create_user(claims)
        return user, True

    async def _create_user(self, claims: SSOClaims):
        username = await self._unique_username(claims)
        return await self.user_repo.create(
            email=claims.email.lower(),
            username=username,
            full_name=claims.full_name or claims.email.split("@", 1)[0],
            hashed_password=None,  # SSO-only account
        )

    async def _unique_username(self, claims: SSOClaims) -> str:
        base = re.sub(r"[^a-z0-9_-]+", "-", claims.email.split("@", 1)[0].lower()).strip("-")
        base = base[:40] or "ssouser"
        candidate = base
        suffix = 1
        while await self.user_repo.get_by_username(candidate):
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    async def _link_identity(
        self, connection: SSOConnection, claims: SSOClaims, user_id: str
    ) -> None:
        from app.database.base import utcnow

        identity = await self.identity_repo.get_by_subject(connection.id, claims.subject)
        if identity is None:
            await self.identity_repo.create(
                connection_id=connection.id,
                user_id=user_id,
                external_subject=claims.subject,
                last_login_at=utcnow(),
            )
        else:
            await self.identity_repo.update(identity, last_login_at=utcnow())

    async def _register_session(
        self, tokens: TokenResponse, *, user_id: str, ip: str = "", user_agent: str | None = None
    ) -> None:
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
            logger.warning("sso_session_register_failed", error=str(exc))
