"""API key issuance, verification and lifecycle.

Keys are shown in plaintext exactly once (at creation/rotation). Only a SHA-256
hash and a non-secret ``prefix`` are persisted. Authentication looks the key up
by prefix, then constant-time compares the hash.

Key format: ``nxk_<random>``. The first 12 characters form the lookup prefix.
"""

from __future__ import annotations

import hashlib
import secrets as _secrets
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base import utcnow
from app.models.identity import ApiKey, ApiKeyPrincipalType, ServiceAccount
from app.models.organization import OrganizationRole
from app.repositories.audit import AuditLogRepository
from app.services.identity import scopes as scope_lib

_KEY_PREFIX = "nxk_"
_PREFIX_LEN = 12


def hash_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _generate_key() -> tuple[str, str, str]:
    """Return ``(plaintext, hashed, prefix)`` for a fresh API key."""
    plaintext = _KEY_PREFIX + _secrets.token_urlsafe(32)
    return plaintext, hash_key(plaintext), plaintext[:_PREFIX_LEN]


@dataclass
class ApiKeyPrincipal:
    """Resolved identity of an authenticated API key."""

    api_key_id: str
    principal_type: str
    organization_id: str | None
    user_id: str | None
    service_account_id: str | None
    role: OrganizationRole | None
    scopes: list[str]


class ApiKeyError(Exception):
    """Raised when an API key cannot be issued or authenticated."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ApiKeyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditLogRepository(session)

    async def create(
        self,
        *,
        principal_type: ApiKeyPrincipalType,
        name: str,
        scopes: list[str] | None,
        organization_id: str | None = None,
        user_id: str | None = None,
        service_account_id: str | None = None,
        expires_at: datetime | None = None,
        created_by: str | None = None,
        actor_user_id: str | None = None,
    ) -> tuple[ApiKey, str]:
        validated = scope_lib.validate_scopes(scopes)

        # Guarantee a unique prefix (collisions are astronomically unlikely).
        for _ in range(5):
            plaintext, hashed, prefix = _generate_key()
            exists = await self.session.scalar(
                select(ApiKey.id).where(ApiKey.prefix == prefix)
            )
            if not exists:
                break
        else:  # pragma: no cover - defensive
            raise ApiKeyError("Could not allocate a unique key prefix", 500)

        key = ApiKey(
            principal_type=principal_type.value,
            organization_id=organization_id,
            user_id=user_id,
            service_account_id=service_account_id,
            name=name,
            prefix=prefix,
            hashed_key=hashed,
            scopes=validated,
            expires_at=expires_at,
            created_by=created_by,
        )
        self.session.add(key)
        await self.session.flush()

        await self.audit.log(
            action="api_key.created",
            resource_type="api_key",
            resource_id=key.id,
            user_id=actor_user_id,
            organization_id=organization_id,
            details={
                "principal_type": principal_type.value,
                "name": name,
                "prefix": prefix,
                "scopes": validated,
            },
        )
        return key, plaintext

    async def list(
        self,
        *,
        organization_id: str | None = None,
        user_id: str | None = None,
        service_account_id: str | None = None,
    ) -> list[ApiKey]:
        stmt = select(ApiKey)
        if service_account_id is not None:
            stmt = stmt.where(ApiKey.service_account_id == service_account_id)
        elif user_id is not None:
            stmt = stmt.where(ApiKey.user_id == user_id)
        elif organization_id is not None:
            stmt = stmt.where(
                ApiKey.organization_id == organization_id,
                ApiKey.principal_type == ApiKeyPrincipalType.ORGANIZATION.value,
            )
        stmt = stmt.order_by(ApiKey.created_at.desc())
        return list((await self.session.scalars(stmt)).all())

    async def get(self, key_id: str) -> ApiKey | None:
        return await self.session.get(ApiKey, key_id)

    async def revoke(self, key: ApiKey, *, actor_user_id: str | None = None) -> ApiKey:
        if key.revoked_at is None:
            key.revoked_at = utcnow()
            self.session.add(key)
            await self.session.flush()
            await self.audit.log(
                action="api_key.revoked",
                resource_type="api_key",
                resource_id=key.id,
                user_id=actor_user_id,
                organization_id=key.organization_id,
                details={"prefix": key.prefix},
            )
        return key

    async def rotate(
        self, key: ApiKey, *, actor_user_id: str | None = None
    ) -> tuple[ApiKey, str]:
        """Revoke the old key and mint a replacement with identical settings."""
        await self.revoke(key, actor_user_id=actor_user_id)
        new_key, plaintext = await self.create(
            principal_type=ApiKeyPrincipalType(key.principal_type),
            name=key.name,
            scopes=key.scopes,
            organization_id=key.organization_id,
            user_id=key.user_id,
            service_account_id=key.service_account_id,
            expires_at=key.expires_at,
            created_by=key.created_by,
            actor_user_id=actor_user_id,
        )
        await self.audit.log(
            action="api_key.rotated",
            resource_type="api_key",
            resource_id=new_key.id,
            user_id=actor_user_id,
            organization_id=key.organization_id,
            details={"old_prefix": key.prefix, "new_prefix": new_key.prefix},
        )
        return new_key, plaintext

    async def authenticate(
        self, token: str, *, ip: str | None = None
    ) -> ApiKeyPrincipal:
        if not token or not token.startswith(_KEY_PREFIX):
            raise ApiKeyError("Invalid API key", 401)
        prefix = token[:_PREFIX_LEN]
        key = await self.session.scalar(select(ApiKey).where(ApiKey.prefix == prefix))
        if key is None:
            raise ApiKeyError("Invalid API key", 401)
        import hmac

        if not hmac.compare_digest(key.hashed_key, hash_key(token)):
            raise ApiKeyError("Invalid API key", 401)
        if key.revoked_at is not None:
            raise ApiKeyError("API key has been revoked", 401)
        if key.expires_at is not None and key.expires_at <= utcnow():
            raise ApiKeyError("API key has expired", 401)

        role: OrganizationRole | None = None
        org_id = key.organization_id

        if key.principal_type == ApiKeyPrincipalType.SERVICE_ACCOUNT.value:
            sa = await self.session.get(ServiceAccount, key.service_account_id)
            if sa is None or sa.disabled:
                raise ApiKeyError("Service account is disabled", 401)
            if sa.expires_at is not None and sa.expires_at <= utcnow():
                raise ApiKeyError("Service account has expired", 401)
            org_id = sa.organization_id
            role = _safe_role(sa.role)
            sa.last_used_at = utcnow()
            self.session.add(sa)
        elif key.principal_type == ApiKeyPrincipalType.ORGANIZATION.value:
            role = OrganizationRole.ADMIN

        key.last_used_at = utcnow()
        if ip:
            key.last_used_ip = ip[:45]
        self.session.add(key)
        await self.session.flush()

        return ApiKeyPrincipal(
            api_key_id=key.id,
            principal_type=key.principal_type,
            organization_id=org_id,
            user_id=key.user_id,
            service_account_id=key.service_account_id,
            role=role,
            scopes=list(key.scopes or [scope_lib.WILDCARD]),
        )


def _safe_role(value: str | None) -> OrganizationRole:
    try:
        return OrganizationRole(str(value))
    except ValueError:
        return OrganizationRole.VIEWER
