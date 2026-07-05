"""Distributed, sliding-window rate limiting.

This module provides the algorithm and storage backends used by
``app.middleware.rate_limit.RateLimitMiddleware`` to throttle abuse-prone
endpoints (authentication, integration connect, webhooks).

Design
------
* **Sliding window log.** Each identity keeps a log of request timestamps. On
  every hit we drop entries older than ``now - window`` and count what remains.
  A request is allowed only when the live count is below the limit, and only an
  *allowed* request is recorded. This is a true sliding window (no fixed-bucket
  burst at window boundaries) and a rejected request never consumes a slot, so a
  client cannot starve itself indefinitely once the window slides.
* **Distributed by default.** :class:`RedisRateLimitBackend` runs the
  check-then-add atomically inside a single Lua script (sorted set), so the
  window is shared across every API replica.
* **Graceful fallback.** When Redis is not configured/installed,
  :func:`get_rate_limit_backend` returns an in-process
  :class:`InMemoryRateLimitBackend` with identical semantics so single-node
  deployments and the test suite keep working.

The ``redis`` package is imported lazily; the application boots fine without it.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import OrderedDict, deque
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


def _record_redis_latency(command: str, seconds: float) -> None:
    """Best-effort Prometheus timing; never affects rate limiting."""
    try:
        from app.observability import metrics

        metrics.observe_redis_latency(command, seconds)
    except Exception:  # pragma: no cover - metrics are optional
        pass


class RateLimitConfigError(ValueError):
    """Raised when a rate-limit spec string cannot be parsed."""


@dataclass(frozen=True)
class RateLimit:
    """A parsed ``"<max_requests>/<window_seconds>"`` specification."""

    limit: int
    window: int

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.limit}/{self.window}"


def parse_rate(spec: str) -> RateLimit:
    """Parse ``"5/60"`` (5 requests per 60 seconds) into a :class:`RateLimit`.

    Raises :class:`RateLimitConfigError` for malformed or non-positive specs so
    misconfiguration fails loudly at startup rather than silently disabling a
    limit.
    """

    raw = (spec or "").strip()
    if "/" not in raw:
        raise RateLimitConfigError(
            f"invalid rate limit spec {spec!r}: expected '<count>/<seconds>'"
        )
    count_str, _, window_str = raw.partition("/")
    try:
        limit = int(count_str.strip())
        window = int(window_str.strip())
    except ValueError as exc:
        raise RateLimitConfigError(
            f"invalid rate limit spec {spec!r}: counts must be integers"
        ) from exc
    if limit <= 0 or window <= 0:
        raise RateLimitConfigError(
            f"invalid rate limit spec {spec!r}: count and window must be > 0"
        )
    return RateLimit(limit=limit, window=window)


@dataclass(frozen=True)
class RateLimitResult:
    """Outcome of a single rate-limit check."""

    allowed: bool
    limit: int
    remaining: int
    # Seconds until the caller is allowed again (when blocked) or until the
    # window fully drains (when allowed). Always >= 0.
    reset_after: float

    @property
    def retry_after(self) -> int:
        """Integer seconds for the ``Retry-After`` header (rounded up, min 1)."""
        return max(1, int(self.reset_after + 0.999)) if not self.allowed else 0


class RateLimitBackend(Protocol):
    """Storage backend implementing the sliding-window check-then-add."""

    async def hit(self, key: str, limit: int, window: int) -> RateLimitResult:
        ...

    async def reset(self, key: str) -> None:
        ...

    async def ping(self) -> bool:
        ...

    async def aclose(self) -> None:
        ...


def _result_from_log(
    timestamps: list[float], now: float, limit: int, window: int, allowed: bool
) -> RateLimitResult:
    count = len(timestamps)
    remaining = max(0, limit - count)
    if timestamps:
        oldest = min(timestamps)
        reset_after = max(0.0, (oldest + window) - now)
    else:
        reset_after = float(window)
    return RateLimitResult(
        allowed=allowed, limit=limit, remaining=remaining, reset_after=reset_after
    )


class InMemoryRateLimitBackend:
    """Process-local sliding-window backend (fallback + test backend).

    Not shared across replicas; intended for single-node deployments, local
    development and tests. Uses an :class:`asyncio.Lock` so concurrent requests
    on the same loop see a consistent window.
    """

    # Hard cap on tracked keys so a high-cardinality / scanning client cannot
    # grow the process heap without bound (the dict is keyed by client IP/user).
    MAX_KEYS = 50_000

    def __init__(self) -> None:
        self._windows: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def hit(self, key: str, limit: int, window: int) -> RateLimitResult:
        now = time.monotonic()
        cutoff = now - window
        async with self._lock:
            bucket = self._windows.get(key)
            if bucket is None:
                bucket = deque()
                self._windows[key] = bucket
            else:
                self._windows.move_to_end(key)
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            allowed = len(bucket) < limit
            if allowed:
                bucket.append(now)
            result = _result_from_log(list(bucket), now, limit, window, allowed)
            # Evict the bucket once its window has fully drained so idle keys do
            # not accumulate; LRU-cap the dict as a backstop against bursts.
            if not bucket:
                self._windows.pop(key, None)
            elif len(self._windows) > self.MAX_KEYS:
                self._windows.popitem(last=False)
            return result

    async def reset(self, key: str) -> None:
        async with self._lock:
            self._windows.pop(key, None)

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:  # pragma: no cover - nothing to close
        self._windows.clear()


# Atomic sliding-window-log in Redis. Returns {allowed, count, reset_after_ms}.
# KEYS[1] = bucket key
# ARGV[1] = now (seconds, float)   ARGV[2] = window (seconds)
# ARGV[3] = limit                  ARGV[4] = unique member
_REDIS_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
local clear_before = now - window
redis.call('ZREMRANGEBYSCORE', key, 0, clear_before)
local count = redis.call('ZCARD', key)
local allowed = 0
if count < limit then
  redis.call('ZADD', key, now, member)
  count = count + 1
  allowed = 1
end
redis.call('PEXPIRE', key, math.ceil(window * 1000))
local reset = window
local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
if oldest[2] then
  reset = (tonumber(oldest[2]) + window) - now
  if reset < 0 then reset = 0 end
end
return {allowed, count, tostring(reset)}
"""


class RedisRateLimitBackend:
    """Distributed sliding-window backend backed by Redis sorted sets."""

    def __init__(self, client: object) -> None:
        # ``client`` is a redis.asyncio.Redis (typed loosely to avoid importing
        # redis at module import time).
        self._client = client
        self._script = client.register_script(_REDIS_SLIDING_WINDOW_LUA)  # type: ignore[attr-defined]

    async def hit(self, key: str, limit: int, window: int) -> RateLimitResult:
        now = time.time()
        member = f"{now:.6f}:{uuid.uuid4().hex}"
        _t0 = time.perf_counter()
        raw = await self._script(keys=[key], args=[now, window, limit, member])
        _record_redis_latency("eval", time.perf_counter() - _t0)
        allowed = bool(int(raw[0]))
        count = int(raw[1])
        reset_after = max(0.0, float(raw[2]))
        remaining = max(0, limit - count)
        return RateLimitResult(
            allowed=allowed, limit=limit, remaining=remaining, reset_after=reset_after
        )

    async def reset(self, key: str) -> None:
        await self._client.delete(key)  # type: ignore[attr-defined]

    async def ping(self) -> bool:
        _t0 = time.perf_counter()
        ok = bool(await self._client.ping())  # type: ignore[attr-defined]
        _record_redis_latency("ping", time.perf_counter() - _t0)
        return ok

    async def aclose(self) -> None:
        try:
            await self._client.aclose()  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - best effort cleanup
            pass


_backend: RateLimitBackend | None = None
_backend_lock = asyncio.Lock()


def _build_redis_backend(redis_url: str) -> RedisRateLimitBackend | None:
    """Try to construct a Redis backend; return ``None`` if unavailable."""
    try:
        import redis.asyncio as redis_asyncio
    except Exception as exc:  # pragma: no cover - depends on environment
        logger.warning(
            "rate_limit_redis_unavailable",
            extra={"error": str(exc), "redis_url": redis_url},
        )
        return None
    try:
        client = redis_asyncio.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    except Exception as exc:  # pragma: no cover - depends on environment
        logger.warning("rate_limit_redis_init_failed", extra={"error": str(exc)})
        return None
    return RedisRateLimitBackend(client)


async def get_rate_limit_backend() -> RateLimitBackend:
    """Return the process-wide rate-limit backend (Redis if configured)."""
    global _backend
    if _backend is not None:
        return _backend
    async with _backend_lock:
        if _backend is not None:
            return _backend
        from app.core.config import settings

        backend: RateLimitBackend | None = None
        if settings.REDIS_URL:
            backend = _build_redis_backend(settings.REDIS_URL)
            if backend is not None:
                logger.info("rate_limit_backend_redis")
        if backend is None:
            if settings.REDIS_URL:
                logger.warning("rate_limit_backend_inmemory_fallback")
            else:
                logger.info("rate_limit_backend_inmemory")
            backend = InMemoryRateLimitBackend()
        _backend = backend
        return _backend


def set_rate_limit_backend(backend: RateLimitBackend | None) -> None:
    """Override the global backend (used by tests)."""
    global _backend
    _backend = backend


async def close_rate_limit_backend() -> None:
    """Close and clear the global backend (called on application shutdown)."""
    global _backend
    if _backend is not None:
        await _backend.aclose()
        _backend = None
