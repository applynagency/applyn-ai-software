"""Distributed locks (mutual exclusion across replicas).

Implements the standard Redis ``SET key token NX PX ttl`` acquire with a
compare-and-delete release (Lua) so a lock is only released by its owner and is
auto-released after ``ttl`` if the holder dies.

When Redis is unavailable a process-local fallback (per-key token) provides the
same API; it only coordinates within a single process, which still prevents
overlapping work for in-process scheduler loops on a single node.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from app.core.config import settings
from app.redis import client as redis_client

logger = logging.getLogger(__name__)

# Compare-and-delete: only release the lock if we still own it.
_RELEASE_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
else
  return 0
end
"""

# Process-local fallback: lock_key -> (token, expire_at_epoch)
_fallback: dict[str, tuple[str, float]] = {}


def _k(name: str) -> str:
    return redis_client.key("lock", name)


def _fallback_acquire(full_key: str, token: str, ttl: int) -> bool:
    now = time.time()
    held = _fallback.get(full_key)
    if held is not None and held[1] > now:
        return False
    _fallback[full_key] = (token, now + ttl)
    return True


def _fallback_release(full_key: str, token: str) -> bool:
    held = _fallback.get(full_key)
    if held is not None and held[0] == token:
        _fallback.pop(full_key, None)
        return True
    return False


async def acquire(name: str, ttl_seconds: int, token: str | None = None) -> str | None:
    """Try once to acquire ``name``. Returns an owner token, or ``None``."""
    if not settings.DISTRIBUTED_LOCK_ENABLED:
        return token or uuid.uuid4().hex
    token = token or uuid.uuid4().hex
    ttl = max(1, int(ttl_seconds))
    full = _k(name)
    client = await redis_client.get_redis()
    if client is not None:
        async with redis_client.timed("lock_acquire"):
            ok = await client.set(full, token, nx=True, ex=ttl)
        acquired = bool(ok)
    else:
        acquired = _fallback_acquire(full, token, ttl)
    _metric(acquired)
    return token if acquired else None


async def release(name: str, token: str) -> bool:
    """Release ``name`` iff still owned by ``token``."""
    if not token:
        return False
    full = _k(name)
    client = await redis_client.get_redis()
    if client is not None:
        async with redis_client.timed("lock_release"):
            try:
                # Atomic compare-and-delete (only the owner releases the lock).
                result = await client.eval(_RELEASE_LUA, 1, full, token)
                return bool(result)
            except Exception:
                # Server without Lua scripting (e.g. fakeredis): fall back to a
                # best-effort GET + conditional DELETE. Slightly racy but bounded
                # by the lock TTL; real Redis always uses the atomic path above.
                current = await client.get(full)
                if current == token:
                    await client.delete(full)
                    return True
                return False
    return _fallback_release(full, token)


def _metric(acquired: bool) -> None:
    try:
        from app.observability import metrics

        metrics.record_lock_attempt(acquired)
    except Exception:  # pragma: no cover - metrics optional
        pass


@asynccontextmanager
async def lock(name: str, ttl_seconds: int | None = None):
    """Best-effort try-lock context manager.

    Yields the owner token when acquired, or ``None`` when the lock is already
    held elsewhere (the caller should skip its work in that case)::

        async with lock("scheduler:monitoring") as token:
            if token is None:
                return  # another replica owns this tick
            ...
    """
    ttl = ttl_seconds if ttl_seconds is not None else settings.SCHEDULER_LOCK_TTL_SECONDS
    token = await acquire(name, ttl)
    try:
        yield token
    finally:
        if token is not None:
            await release(name, token)


def scheduler_lock(name: str):
    """Try-lock for a scheduler tick (skips the tick when held elsewhere)."""
    return lock(f"scheduler:{name}", settings.SCHEDULER_LOCK_TTL_SECONDS)


async def renew(name: str, token: str, ttl_seconds: int) -> bool:
    """Extend ``name``'s lease iff still owned by ``token`` (leader renewal)."""
    if not token:
        return False
    full = _k(name)
    ttl = max(1, int(ttl_seconds))
    client = await redis_client.get_redis()
    if client is not None:
        try:
            result = await client.eval(_RENEW_LUA, 1, full, token, str(ttl))
            return bool(result)
        except Exception:
            current = await client.get(full)
            if current == token:
                await client.set(full, token, ex=ttl)
                return True
            return False
    held = _fallback.get(full)
    if held is not None and held[0] == token:
        _fallback[full] = (token, time.time() + ttl)
        return True
    return False


# Compare-and-extend: only renew the lease if we still own it.
_RENEW_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('EXPIRE', KEYS[1], ARGV[2])
else
  return 0
end
"""


class LeaderElector:
    """Sticky leader election with background lease renewal.

    One replica becomes leader by acquiring a lock; it renews the lease on an
    interval (well within the TTL). If the leader dies the lease expires and
    another replica takes over. Use for singleton responsibilities that must run
    on exactly one node (e.g. a dedicated scheduler/beat process).
    """

    def __init__(self, name: str, *, ttl_seconds: int = 30, renew_interval: float | None = None):
        self.name = f"leader:{name}"
        self.ttl_seconds = ttl_seconds
        self.renew_interval = renew_interval or max(1.0, ttl_seconds / 3)
        self._token: str | None = None
        self._task = None

    @property
    def is_leader(self) -> bool:
        return self._token is not None

    async def try_acquire(self) -> bool:
        if self._token is not None:
            # Already leader — confirm the lease is still ours.
            if await renew(self.name, self._token, self.ttl_seconds):
                return True
            self._token = None
        token = await acquire(self.name, self.ttl_seconds)
        self._token = token
        return token is not None

    async def start(self) -> None:
        """Run a background loop that maintains leadership best-effort."""
        import asyncio

        async def _loop():
            while True:
                try:
                    await self.try_acquire()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("leader_election_error", extra={"error": str(exc)})
                await asyncio.sleep(self.renew_interval)

        import asyncio as _asyncio

        self._task = _asyncio.create_task(_loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except Exception:  # pragma: no cover - best effort
                pass
            self._task = None
        if self._token is not None:
            await release(self.name, self._token)
            self._token = None


def clear_fallback() -> None:
    """Clear the in-process fallback store (used by tests)."""
    _fallback.clear()
