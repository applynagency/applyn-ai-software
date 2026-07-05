"""Operations platform (Sprint 62B).

Day-2 operational controls, all backed by the unified :class:`ConfigService`
(global scope) so they apply across every replica without a redeploy:

* maintenance mode      — short-circuit traffic with 503 during planned windows
* kill switches         — disable a named subsystem instantly (incident response)
* rolling feature rollout — deterministic percentage rollout keyed by org id
* support bundle        — collect non-sensitive diagnostics for support tickets
* configuration export/import — snapshot + restore global/org config

A tiny process-local TTL cache fronts the maintenance/kill-switch reads so the
middleware does not hit the database on every request.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.platform.config import ConfigService

logger = get_logger(__name__)

MAINTENANCE_KEY = "ops.maintenance_mode"
KILL_PREFIX = "ops.kill."
ROLLOUT_PREFIX = "ops.rollout."

# Process-local cache: {key: (value, expires_at)}. Bounded by the small number
# of ops keys, refreshed every OPS_STATE_CACHE_TTL_SECONDS.
_CACHE: dict[str, tuple[Any, float]] = {}


def _cache_get(key: str):
    item = _CACHE.get(key)
    if item is None:
        return None, False
    value, expires = item
    if time.monotonic() >= expires:
        return None, False
    return value, True


def _cache_set(key: str, value: Any) -> None:
    ttl = max(0.5, float(settings.OPS_STATE_CACHE_TTL_SECONDS))
    _CACHE[key] = (value, time.monotonic() + ttl)


def clear_cache() -> None:  # test helper
    _CACHE.clear()


class OperationsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.config = ConfigService(session)

    # --------------------------------------------------------- maintenance
    async def set_maintenance(self, enabled: bool, *, message: str | None = None,
                              updated_by: str | None = None) -> dict:
        await self.config.set(
            key=MAINTENANCE_KEY,
            value={"enabled": bool(enabled),
                   "message": message or settings.MAINTENANCE_MODE_MESSAGE},
            updated_by=updated_by)
        clear_cache()
        return {"enabled": bool(enabled), "message": message}

    async def maintenance_status(self) -> dict:
        cached, ok = _cache_get(MAINTENANCE_KEY)
        if ok:
            return cached
        value = await self.config.get(MAINTENANCE_KEY, default=None)
        if value is None:
            status = {"enabled": settings.MAINTENANCE_MODE_ENABLED,
                      "message": settings.MAINTENANCE_MODE_MESSAGE}
        else:
            status = {"enabled": bool(value.get("enabled")),
                      "message": value.get("message") or settings.MAINTENANCE_MODE_MESSAGE}
        _cache_set(MAINTENANCE_KEY, status)
        return status

    # --------------------------------------------------------- kill switches
    async def set_kill_switch(self, name: str, enabled: bool, *,
                              updated_by: str | None = None) -> dict:
        await self.config.set(key=f"{KILL_PREFIX}{name}", value=bool(enabled),
                              updated_by=updated_by)
        clear_cache()
        return {"name": name, "killed": bool(enabled)}

    async def is_killed(self, name: str) -> bool:
        key = f"{KILL_PREFIX}{name}"
        cached, ok = _cache_get(key)
        if ok:
            return cached
        value = await self.config.get_flag(key, default=False)
        _cache_set(key, value)
        return value

    # --------------------------------------------------------- feature rollout
    async def set_rollout(self, feature: str, percent: int, *,
                          updated_by: str | None = None) -> dict:
        percent = max(0, min(100, int(percent)))
        await self.config.set(key=f"{ROLLOUT_PREFIX}{feature}", value=percent,
                              updated_by=updated_by)
        return {"feature": feature, "percent": percent}

    async def is_rolled_out(self, feature: str, *, organization_id: str | None) -> bool:
        """Deterministic percentage rollout: stable per (feature, org)."""
        percent = int(await self.config.get(
            f"{ROLLOUT_PREFIX}{feature}", default=0) or 0)
        if percent >= 100:
            return True
        if percent <= 0:
            return False
        bucket = _bucket(f"{feature}:{organization_id or 'global'}")
        return bucket < percent

    # --------------------------------------------------------- diagnostics
    async def diagnostics(self) -> dict:
        """Runtime diagnostics snapshot (no secrets)."""
        from app.platform.region import current_region

        info: dict[str, Any] = {
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "region": current_region(),
            "maintenance": await self.maintenance_status(),
            "flags": {
                "job_queue": settings.JOB_QUEUE_ENABLED,
                "event_consumer": settings.EVENT_CONSUMER_ENABLED,
                "ai_platform": settings.AI_PLATFORM_ENABLED,
                "billing": settings.BILLING_ENABLED,
                "search_index": settings.SEARCH_INDEX_ENABLED,
            },
        }
        try:
            from app.core import health

            overall, checks = await health.run_checks(health.READINESS_CHECKS)
            info["health"] = {"overall": overall,
                              "checks": [c.to_dict() for c in checks]}
        except Exception as exc:  # noqa: BLE001
            info["health"] = {"error": str(exc)}
        return info

    async def support_bundle(self, *, organization_id: str | None = None) -> dict:
        """Assemble a non-sensitive support bundle for a ticket."""
        bundle: dict[str, Any] = {
            "generated_at": _now_iso(),
            "diagnostics": await self.diagnostics(),
        }
        try:
            bundle["ai_provider_health"] = _ai_health_snapshot()
        except Exception:  # noqa: BLE001
            bundle["ai_provider_health"] = []
        try:
            from app.platform.execution import ExecutionEngine

            bundle["execution"] = await ExecutionEngine(self.session).analytics(
                organization_id=organization_id)
        except Exception as exc:  # noqa: BLE001
            bundle["execution"] = {"error": str(exc)}
        return bundle

    # --------------------------------------------------------- config io
    async def export_config(self, *, organization_id: str | None = None) -> dict:
        from sqlalchemy import select

        from app.models.platform_core import ConfigEntry, ConfigScope

        scopes = [(ConfigScope.GLOBAL.value, None)]
        if organization_id:
            scopes.append((ConfigScope.ORGANIZATION.value, organization_id))
        entries = []
        for scope, scope_id in scopes:
            rows = (await self.session.execute(
                select(ConfigEntry).where(
                    ConfigEntry.scope == scope,
                    ConfigEntry.scope_id == scope_id,
                ))).scalars().all()
            for row in rows:
                if row.is_secret_ref:
                    continue  # never export secret references
                entries.append({
                    "scope": row.scope, "scope_id": row.scope_id, "key": row.key,
                    "value": ConfigService._unwrap(row),
                    "is_feature_flag": row.is_feature_flag,
                })
        return {"version": 1, "exported_at": _now_iso(), "entries": entries}

    async def import_config(self, bundle: dict, *, updated_by: str | None = None) -> int:
        count = 0
        for entry in bundle.get("entries", []):
            try:
                await self.config.set(
                    key=entry["key"], value=entry.get("value"),
                    scope=entry.get("scope", "global"),
                    scope_id=entry.get("scope_id"),
                    is_feature_flag=bool(entry.get("is_feature_flag")),
                    updated_by=updated_by)
                count += 1
            except Exception as exc:  # noqa: BLE001 - skip a bad row, keep going
                logger.warning("config_import_skip", key=entry.get("key"), error=str(exc))
        clear_cache()
        return count


def _bucket(value: str) -> int:
    h = hashlib.sha256(value.encode()).hexdigest()
    return int(h[:8], 16) % 100


def _now_iso() -> str:
    from app.database.base import utcnow

    return utcnow().isoformat()


def _ai_health_snapshot() -> list[dict]:
    from app.ai.health import get_provider_health

    return get_provider_health().snapshot()
