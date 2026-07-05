"""Arq Redis pool management.

Lazily builds (and caches) a single Arq Redis pool for the API process so the
trigger endpoints can enqueue jobs. Returns ``None`` whenever the queue is not
usable (queue disabled, no Redis URL, or ``arq`` not installed) — callers then
fall back to inline execution.
"""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

_pool = None  # type: ignore[var-annotated]
_pool_unavailable = False


def _redis_dsn() -> str | None:
    return settings.JOB_QUEUE_REDIS_URL or settings.REDIS_URL


def redis_settings():
    """Build an Arq ``RedisSettings`` from the configured DSN (or None)."""
    dsn = _redis_dsn()
    if not dsn:
        return None
    from arq.connections import RedisSettings

    return RedisSettings.from_dsn(dsn)


async def get_arq_pool():
    """Return a cached Arq pool, or ``None`` if the queue is unavailable."""
    global _pool, _pool_unavailable
    if not settings.JOB_QUEUE_ENABLED:
        return None
    if _pool is not None:
        return _pool
    if _pool_unavailable:
        return None
    rs = redis_settings()
    if rs is None:
        logger.warning("job_queue_enabled_without_redis_url")
        _pool_unavailable = True
        return None
    try:
        from arq import create_pool

        _pool = await create_pool(rs)
        return _pool
    except Exception as exc:  # pragma: no cover - defensive (arq/redis missing)
        logger.error("job_queue_pool_init_failed", extra={"error": str(exc)})
        _pool_unavailable = True
        return None


async def close_arq_pool() -> None:
    global _pool, _pool_unavailable
    if _pool is not None:
        try:
            await _pool.aclose()
        except Exception:  # pragma: no cover - defensive
            pass
        _pool = None
    _pool_unavailable = False
