"""TTL'd application cache.

Redis-backed when configured; otherwise a process-local TTL dict with identical
semantics. Values are JSON-serialized. All keys are namespaced under
``<prefix>:cache:``. Records hit/miss metrics.

Typical use::

    from app.redis import cache

    data = await cache.get_or_set("integrations:catalog", 300, load_catalog)
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.config import settings
from app.redis import client as redis_client

logger = logging.getLogger(__name__)

# Process-local fallback: key -> (expire_at_epoch | None, json_value)
_fallback: dict[str, tuple[float | None, str]] = {}


def _k(key: str) -> str:
    return redis_client.key("cache", key)


def _metric(event: str) -> None:
    try:
        from app.observability import metrics

        metrics.record_cache_event(event)
    except Exception:  # pragma: no cover - metrics optional
        pass


def _fallback_get(full_key: str) -> str | None:
    entry = _fallback.get(full_key)
    if entry is None:
        return None
    expire_at, value = entry
    if expire_at is not None and expire_at <= time.time():
        _fallback.pop(full_key, None)
        return None
    return value


# Cap on the process-local cache so rotating keys (e.g. time-bucketed counters)
# cannot accumulate without bound while Redis is unavailable.
_FALLBACK_MAXLEN = 10_000


def _fallback_sweep() -> None:
    now = time.time()
    expired = [k for k, (exp, _) in _fallback.items() if exp is not None and exp <= now]
    for k in expired:
        _fallback.pop(k, None)
    # Backstop: if still over the cap, drop arbitrary (oldest-inserted) entries.
    while len(_fallback) > _FALLBACK_MAXLEN:
        try:
            _fallback.pop(next(iter(_fallback)))
        except StopIteration:  # pragma: no cover - defensive
            break


def _fallback_set(full_key: str, value: str, ttl: int | None) -> None:
    expire_at = time.time() + ttl if ttl and ttl > 0 else None
    if full_key not in _fallback and len(_fallback) >= _FALLBACK_MAXLEN:
        _fallback_sweep()
    _fallback[full_key] = (expire_at, value)


async def get(key: str, default: Any = None) -> Any:
    if not settings.CACHE_ENABLED:
        return default
    full = _k(key)
    raw: str | None
    client = await redis_client.get_redis()
    if client is not None:
        async with redis_client.timed("get"):
            raw = await client.get(full)
    else:
        raw = _fallback_get(full)
    if raw is None:
        _metric("miss")
        return default
    _metric("hit")
    try:
        return json.loads(raw)
    except (ValueError, TypeError):  # pragma: no cover - defensive
        return default


async def set(key: str, value: Any, ttl: int | None = None) -> None:
    if not settings.CACHE_ENABLED:
        return
    if ttl is None:
        ttl = settings.CACHE_DEFAULT_TTL_SECONDS
    full = _k(key)
    raw = json.dumps(value, default=str)
    client = await redis_client.get_redis()
    if client is not None:
        async with redis_client.timed("set"):
            if ttl and ttl > 0:
                await client.set(full, raw, ex=ttl)
            else:
                await client.set(full, raw)
    else:
        _fallback_set(full, raw, ttl)


async def delete(key: str) -> None:
    full = _k(key)
    client = await redis_client.get_redis()
    if client is not None:
        async with redis_client.timed("delete"):
            await client.delete(full)
    else:
        _fallback.pop(full, None)


async def exists(key: str) -> bool:
    full = _k(key)
    client = await redis_client.get_redis()
    if client is not None:
        async with redis_client.timed("exists"):
            return bool(await client.exists(full))
    return _fallback_get(full) is not None


async def incr(key: str, amount: int = 1, ttl: int | None = None) -> int:
    """Atomically increment an integer counter, returning the new value."""
    full = _k(key)
    client = await redis_client.get_redis()
    if client is not None:
        async with redis_client.timed("incr"):
            value = int(await client.incrby(full, amount))
            if ttl and ttl > 0:
                await client.expire(full, ttl)
            return value
    current = 0
    raw = _fallback_get(full)
    if raw is not None:
        try:
            current = int(json.loads(raw))
        except (ValueError, TypeError):
            current = 0
    current += amount
    _fallback_set(full, json.dumps(current), ttl)
    return current


async def get_or_set(
    key: str, ttl: int | None, factory: Callable[[], Awaitable[Any] | Any]
) -> Any:
    """Return the cached value, or compute it via ``factory`` and cache it.

    ``factory`` may be sync or async. On a miss the value is stored with ``ttl``.
    Caching is skipped (factory result returned directly) when disabled.
    """
    if not settings.CACHE_ENABLED:
        result = factory()
        if hasattr(result, "__await__"):
            result = await result
        return result
    sentinel = object()
    cached_value = await get(key, default=sentinel)
    if cached_value is not sentinel:
        return cached_value
    result = factory()
    if hasattr(result, "__await__"):
        result = await result
    await set(key, result, ttl)
    return result


# --- versioned namespaces (bulk invalidation) -------------------------------
#
# A namespace carries a monotonically increasing version counter. The version is
# embedded into every key, so bumping the counter atomically invalidates the
# whole namespace in O(1) without scanning/deleting individual keys. Entries age
# out naturally via their TTL.


def _version_key(namespace: str) -> str:
    return f"__ver__:{namespace}"


async def get_version(namespace: str) -> int:
    raw = await get(_version_key(namespace), default=0)
    try:
        return int(raw)
    except (ValueError, TypeError):  # pragma: no cover - defensive
        return 0


async def bump_version(namespace: str) -> int:
    """Invalidate an entire namespace by incrementing its version counter."""
    return await incr(_version_key(namespace))


# ``invalidate`` is the public name callers use after a write.
invalidate = bump_version


async def versioned_key(namespace: str, *parts: str) -> str:
    version = await get_version(namespace)
    suffix = ":".join(p for p in parts if p)
    return f"{namespace}:v{version}:{suffix}"


async def versioned_get(namespace: str, *parts: str, default: Any = None) -> Any:
    return await get(await versioned_key(namespace, *parts), default=default)


async def versioned_set(
    namespace: str, *parts: str, value: Any, ttl: int | None = None
) -> None:
    await set(await versioned_key(namespace, *parts), value, ttl=ttl)


async def versioned_get_or_set(
    namespace: str,
    *parts: str,
    ttl: int | None,
    factory: Callable[[], Awaitable[Any] | Any],
) -> Any:
    return await get_or_set(await versioned_key(namespace, *parts), ttl, factory)


async def delete_prefix(prefix: str) -> int:
    """Best-effort delete of every key matching ``<cache-ns>:<prefix>*``.

    Uses SCAN (non-blocking) on Redis; sweeps the fallback dict otherwise.
    """
    full_prefix = _k(prefix)
    client = await redis_client.get_redis()
    deleted = 0
    if client is not None:
        async with redis_client.timed("scan_delete"):
            async for k in client.scan_iter(match=f"{full_prefix}*", count=200):
                await client.delete(k)
                deleted += 1
        return deleted
    for k in [k for k in _fallback if k.startswith(full_prefix)]:
        _fallback.pop(k, None)
        deleted += 1
    return deleted


def clear_fallback() -> None:
    """Clear the in-process fallback store (used by tests)."""
    _fallback.clear()
