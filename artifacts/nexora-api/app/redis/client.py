"""Shared async Redis client.

Builds (and caches) a single ``redis.asyncio.Redis`` connection pool from
``settings.REDIS_URL`` for the whole process. Returns ``None`` whenever Redis is
not usable (no URL, or the ``redis`` package is unavailable) so every consumer
can fall back to an in-process implementation.

The ``redis`` package is imported lazily; the app boots fine without it.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from app.core.config import settings

logger = logging.getLogger(__name__)

_client = None  # redis.asyncio.Redis | None
_unavailable = False
# Monotonic time after which a failed client may be re-probed (auto-reconnect).
_retry_after = 0.0
# Cooldown between reconnect attempts so we don't hammer a down Redis.
_RECONNECT_COOLDOWN_SECONDS = 5.0


def _record_latency(command: str, seconds: float) -> None:
    try:
        from app.observability import metrics

        metrics.observe_redis_latency(command, seconds)
    except Exception:  # pragma: no cover - metrics optional
        pass


def _build_client():
    try:
        import redis.asyncio as redis_asyncio
    except Exception as exc:  # pragma: no cover - depends on environment
        logger.warning("redis_package_unavailable", extra={"error": str(exc)})
        return None
    try:
        return redis_asyncio.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            socket_connect_timeout=2,
            socket_timeout=2,
            health_check_interval=30,
        )
    except Exception as exc:  # pragma: no cover - depends on environment
        logger.warning("redis_client_init_failed", extra={"error": str(exc)})
        return None


def _mark_unavailable() -> None:
    """Latch a transient outage with a cooldown so we re-probe later."""
    global _unavailable, _retry_after
    _unavailable = True
    _retry_after = time.monotonic() + _RECONNECT_COOLDOWN_SECONDS


async def get_redis():
    """Return the shared Redis client, or ``None`` when Redis is unavailable.

    When a previous attempt failed we re-probe after a short cooldown so the
    process automatically reconnects once Redis comes back (no restart needed).
    """
    global _client, _unavailable, _retry_after
    if _client is not None:
        return _client
    if not settings.REDIS_URL:
        _unavailable = True
        return None
    if _unavailable and time.monotonic() < _retry_after:
        return None
    client = _build_client()
    if client is None:
        _mark_unavailable()
        return None
    _client = client
    _unavailable = False
    logger.info("redis_client_ready")
    return _client


async def drop_client() -> None:
    """Discard the cached client after an operational error so the next call
    re-probes the connection (auto-reconnect on the following request)."""
    global _client
    if _client is not None:
        try:
            await _client.aclose()
        except Exception:  # pragma: no cover - best effort
            pass
        _client = None
    _mark_unavailable()


def set_redis_client(client) -> None:
    """Override the shared client (used by tests). Pass ``None`` to reset."""
    global _client, _unavailable, _retry_after
    _client = client
    _unavailable = False
    _retry_after = 0.0


async def close_redis() -> None:
    global _client, _unavailable, _retry_after
    if _client is not None:
        try:
            await _client.aclose()
        except Exception:  # pragma: no cover - best effort
            pass
        _client = None
    _unavailable = False
    _retry_after = 0.0


async def ping() -> bool:
    client = await get_redis()
    if client is None:
        return False
    t0 = time.perf_counter()
    try:
        ok = bool(await client.ping())
    finally:
        _record_latency("ping", time.perf_counter() - t0)
    return ok


def key(*parts: str) -> str:
    """Build a namespaced key, e.g. ``key("cache", "x") -> "nexora:cache:x"``."""
    return ":".join((settings.REDIS_KEY_PREFIX, *[p for p in parts if p != ""]))


@asynccontextmanager
async def timed(command: str):
    """Time a Redis command for the ``nexora_redis_command_duration`` metric."""
    t0 = time.perf_counter()
    try:
        yield
    finally:
        _record_latency(command, time.perf_counter() - t0)
