"""Configuration platform (Sprint 62A).

ONE configuration service with three scopes and clear inheritance::

    global  ↓  organization  ↓  user

A ``get`` resolves the most specific value available (user > organization >
global). Supports feature flags and secret references (the stored value is a
reference like ``secret://name`` that is resolved by the secrets subsystem).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_core import ConfigEntry, ConfigScope


class ConfigService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def set(
        self,
        *,
        key: str,
        value: Any,
        scope: str = ConfigScope.GLOBAL.value,
        scope_id: str | None = None,
        is_feature_flag: bool = False,
        is_secret_ref: bool = False,
        updated_by: str | None = None,
    ) -> ConfigEntry:
        scope = str(getattr(scope, "value", scope))
        if scope == ConfigScope.GLOBAL.value:
            scope_id = None
        elif not scope_id:
            raise ValueError(f"scope_id is required for scope '{scope}'")
        existing = (await self.session.execute(
            select(ConfigEntry).where(
                ConfigEntry.scope == scope,
                ConfigEntry.scope_id == scope_id,
                ConfigEntry.key == key,
            ))).scalar_one_or_none()
        if existing:
            existing.value = {"v": value}
            existing.is_feature_flag = is_feature_flag
            existing.is_secret_ref = is_secret_ref
            existing.updated_by = updated_by
        else:
            existing = ConfigEntry(
                scope=scope, scope_id=scope_id, key=key, value={"v": value},
                is_feature_flag=is_feature_flag, is_secret_ref=is_secret_ref,
                updated_by=updated_by)
            self.session.add(existing)
        await self.session.flush()
        return existing

    @staticmethod
    def _unwrap(entry: ConfigEntry | None) -> Any:
        if entry is None or entry.value is None:
            return None
        if isinstance(entry.value, dict) and "v" in entry.value:
            return entry.value["v"]
        return entry.value

    async def _entry(self, scope: str, scope_id: str | None, key: str) -> ConfigEntry | None:
        return (await self.session.execute(
            select(ConfigEntry).where(
                ConfigEntry.scope == scope,
                ConfigEntry.scope_id == scope_id,
                ConfigEntry.key == key,
            ))).scalar_one_or_none()

    async def get(
        self,
        key: str,
        *,
        organization_id: str | None = None,
        user_id: str | None = None,
        default: Any = None,
    ) -> Any:
        # Most specific wins: user → organization → global.
        if user_id:
            entry = await self._entry(ConfigScope.USER.value, user_id, key)
            if entry is not None:
                return self._unwrap(entry)
        if organization_id:
            entry = await self._entry(ConfigScope.ORGANIZATION.value, organization_id, key)
            if entry is not None:
                return self._unwrap(entry)
        entry = await self._entry(ConfigScope.GLOBAL.value, None, key)
        if entry is not None:
            return self._unwrap(entry)
        return default

    async def get_flag(
        self, key: str, *, organization_id: str | None = None,
        user_id: str | None = None, default: bool = False,
    ) -> bool:
        value = await self.get(key, organization_id=organization_id,
                               user_id=user_id, default=default)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}
        return bool(value)

    async def resolve_all(
        self, *, organization_id: str | None = None, user_id: str | None = None,
    ) -> dict[str, Any]:
        """Return the fully-merged effective configuration for a user/org."""
        merged: dict[str, Any] = {}
        # Apply least-specific first so more-specific scopes overwrite.
        layers: list[tuple[str, str | None]] = [(ConfigScope.GLOBAL.value, None)]
        if organization_id:
            layers.append((ConfigScope.ORGANIZATION.value, organization_id))
        if user_id:
            layers.append((ConfigScope.USER.value, user_id))
        for scope, scope_id in layers:
            rows = (await self.session.execute(
                select(ConfigEntry).where(
                    ConfigEntry.scope == scope,
                    ConfigEntry.scope_id == scope_id,
                ))).scalars().all()
            for row in rows:
                merged[row.key] = self._unwrap(row)
        return merged

    async def delete(self, key: str, *, scope: str, scope_id: str | None = None) -> bool:
        scope = str(getattr(scope, "value", scope))
        if scope == ConfigScope.GLOBAL.value:
            scope_id = None
        entry = await self._entry(scope, scope_id, key)
        if entry is None:
            return False
        await self.session.delete(entry)
        await self.session.flush()
        return True
