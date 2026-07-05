"""Organization configuration variables — secrets encrypted, config values plain."""

from __future__ import annotations

import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models.user import User
from app.repositories.org_config import OrgConfigRepository
from app.security.secrets.crypto import get_cipher
from app.tenancy.permissions import can_read_resources, can_write_resources


class OrgConfigService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = OrgConfigRepository(session)
        self._cipher = None

    @property
    def cipher(self):
        if self._cipher is None:
            self._cipher = get_cipher()
        return self._cipher

    def _ensure_read(self, user: User, org_context: OrgContext) -> None:
        if not user.is_superuser and (not org_context.role or not can_read_resources(org_context.role)):
            raise ForbiddenError()

    def _ensure_write(self, user: User, org_context: OrgContext) -> None:
        if not user.is_superuser and (not org_context.role or not can_write_resources(org_context.role)):
            raise ForbiddenError()

    def _encrypt(self, value: str) -> str:
        return self.cipher.encrypt(json.dumps({"v": value}, separators=(",", ":")))

    @staticmethod
    def _view(row) -> dict:
        preview = None
        if row.is_secret:
            preview = "••••••"
        elif row.value_plain:
            preview = row.value_plain[:80] + ("…" if len(row.value_plain) > 80 else "")
        return {
            "id": row.id,
            "key": row.key,
            "environment": row.environment,
            "description": row.description,
            "is_secret": row.is_secret,
            "has_value": bool(row.value_encrypted or row.value_plain),
            "value_preview": preview,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    async def list_variables(self, user, org_context, environment: str | None = None) -> list[dict]:
        self._ensure_read(user, org_context)
        org_id = org_context.requires_organization
        rows = await self.repo.list_for_org(org_id, environment=environment)
        return [self._view(r) for r in rows]

    async def create_variable(self, user, org_context, payload) -> dict:
        self._ensure_write(user, org_context)
        org_id = org_context.requires_organization
        key = payload.key.strip()
        if not key:
            raise ValidationError("Variable key is required.")
        existing = await self.repo.get_by_key(org_id, key, payload.environment)
        if existing:
            raise ValidationError(f"Variable '{key}' already exists for environment '{payload.environment}'.")
        kwargs = {
            "organization_id": org_id,
            "key": key,
            "environment": payload.environment,
            "description": payload.description,
            "is_secret": payload.is_secret,
            "created_by": user.id,
            "updated_by": user.id,
        }
        if payload.is_secret:
            kwargs["value_encrypted"] = self._encrypt(payload.value)
            kwargs["value_plain"] = None
        else:
            kwargs["value_plain"] = payload.value
            kwargs["value_encrypted"] = None
        row = await self.repo.create(**kwargs)
        return self._view(row)

    async def update_variable(self, user, org_context, variable_id: str, payload) -> dict:
        self._ensure_write(user, org_context)
        org_id = org_context.requires_organization
        row = await self.repo.get_for_org(variable_id, org_id)
        if not row:
            raise NotFoundError("Variable", variable_id)
        updates: dict = {"updated_by": user.id}
        if payload.description is not None:
            updates["description"] = payload.description
        if payload.is_secret is not None:
            updates["is_secret"] = payload.is_secret
        if payload.value is not None:
            is_secret = payload.is_secret if payload.is_secret is not None else row.is_secret
            if is_secret:
                updates["value_encrypted"] = self._encrypt(payload.value)
                updates["value_plain"] = None
            else:
                updates["value_plain"] = payload.value
                updates["value_encrypted"] = None
        row = await self.repo.update(row, **updates)
        return self._view(row)

    async def delete_variable(self, user, org_context, variable_id: str) -> None:
        self._ensure_write(user, org_context)
        org_id = org_context.requires_organization
        row = await self.repo.get_for_org(variable_id, org_id)
        if not row:
            raise NotFoundError("Variable", variable_id)
        await self.repo.delete(row)
