"""Service account lifecycle (create, rotate secrets, disable, expire, audit)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base import utcnow
from app.models.identity import ApiKey, ApiKeyPrincipalType, ServiceAccount
from app.models.organization import OrganizationRole
from app.repositories.audit import AuditLogRepository
from app.services.identity import scopes as scope_lib
from app.services.identity.api_keys import ApiKeyError, ApiKeyService


class ServiceAccountService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditLogRepository(session)
        self.keys = ApiKeyService(session)

    async def create(
        self,
        *,
        organization_id: str,
        name: str,
        description: str | None,
        role: OrganizationRole,
        scopes: list[str] | None,
        expires_at: datetime | None = None,
        actor_user_id: str | None = None,
    ) -> ServiceAccount:
        existing = await self.session.scalar(
            select(ServiceAccount.id).where(
                ServiceAccount.organization_id == organization_id,
                ServiceAccount.name == name,
            )
        )
        if existing:
            raise ApiKeyError("A service account with that name already exists", 409)

        sa = ServiceAccount(
            organization_id=organization_id,
            name=name,
            description=description,
            role=role.value,
            scopes=scope_lib.validate_scopes(scopes),
            expires_at=expires_at,
            created_by=actor_user_id,
        )
        self.session.add(sa)
        await self.session.flush()
        await self.audit.log(
            action="service_account.created",
            resource_type="service_account",
            resource_id=sa.id,
            user_id=actor_user_id,
            organization_id=organization_id,
            details={"name": name, "role": role.value, "scopes": sa.scopes},
        )
        return sa

    async def list(self, organization_id: str) -> list[ServiceAccount]:
        stmt = (
            select(ServiceAccount)
            .where(ServiceAccount.organization_id == organization_id)
            .order_by(ServiceAccount.created_at.desc())
        )
        return list((await self.session.scalars(stmt)).all())

    async def get(self, organization_id: str, sa_id: str) -> ServiceAccount | None:
        sa = await self.session.get(ServiceAccount, sa_id)
        if sa is None or sa.organization_id != organization_id:
            return None
        return sa

    async def update(
        self,
        sa: ServiceAccount,
        *,
        description: str | None = None,
        role: OrganizationRole | None = None,
        scopes: list[str] | None = None,
        disabled: bool | None = None,
        expires_at: datetime | None = None,
        clear_expiry: bool = False,
        actor_user_id: str | None = None,
    ) -> ServiceAccount:
        if description is not None:
            sa.description = description
        if role is not None:
            sa.role = role.value
        if scopes is not None:
            sa.scopes = scope_lib.validate_scopes(scopes)
        if disabled is not None:
            sa.disabled = disabled
        if clear_expiry:
            sa.expires_at = None
        elif expires_at is not None:
            sa.expires_at = expires_at
        self.session.add(sa)
        await self.session.flush()
        await self.audit.log(
            action="service_account.updated",
            resource_type="service_account",
            resource_id=sa.id,
            user_id=actor_user_id,
            organization_id=sa.organization_id,
            details={"disabled": sa.disabled, "role": sa.role},
        )
        return sa

    async def disable(
        self, sa: ServiceAccount, *, actor_user_id: str | None = None
    ) -> ServiceAccount:
        sa.disabled = True
        self.session.add(sa)
        # Revoke all outstanding keys when disabling.
        keys = await self.session.scalars(
            select(ApiKey).where(
                ApiKey.service_account_id == sa.id, ApiKey.revoked_at.is_(None)
            )
        )
        for key in keys.all():
            key.revoked_at = utcnow()
            self.session.add(key)
        await self.session.flush()
        await self.audit.log(
            action="service_account.disabled",
            resource_type="service_account",
            resource_id=sa.id,
            user_id=actor_user_id,
            organization_id=sa.organization_id,
        )
        return sa

    async def issue_key(
        self,
        sa: ServiceAccount,
        *,
        name: str,
        scopes: list[str] | None = None,
        expires_at: datetime | None = None,
        actor_user_id: str | None = None,
    ) -> tuple[ApiKey, str]:
        if sa.disabled:
            raise ApiKeyError("Cannot issue a key for a disabled service account", 409)
        # A service-account key may only narrow the account's own scopes.
        key_scopes = scope_lib.validate_scopes(scopes) if scopes else list(sa.scopes or [])
        return await self.keys.create(
            principal_type=ApiKeyPrincipalType.SERVICE_ACCOUNT,
            name=name,
            scopes=key_scopes or None,
            organization_id=sa.organization_id,
            service_account_id=sa.id,
            expires_at=expires_at or sa.expires_at,
            created_by=actor_user_id,
            actor_user_id=actor_user_id,
        )

    async def list_keys(self, sa: ServiceAccount) -> list[ApiKey]:
        return await self.keys.list(service_account_id=sa.id)
