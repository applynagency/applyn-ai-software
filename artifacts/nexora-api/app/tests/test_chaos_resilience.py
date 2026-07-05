"""Chaos & resilience tests (Sprint 61B).

Validates the production-HA primitives without requiring a real Redis/Postgres:
* Redis-unavailable graceful fallback (cache/locks keep working).
* Redis auto-reconnect after a transient outage (cooldown re-probe).
* Circuit breaker open/half-open/closed recovery (no cascading failures).
* Bulkhead bounded-concurrency isolation.
* Distributed leader election (single winner) + lease renewal.
* Versioned cache invalidation.
* Job priority-queue routing + delayed-job parameters.
"""

from __future__ import annotations

import asyncio

import pytest

from app.core.config import settings
from app.redis import cache, locks
from app.redis import client as rc

# --- Redis unavailable: graceful fallback ------------------------------------


async def test_cache_fallback_when_redis_unavailable():
    # No Redis client -> in-process fallback must still satisfy reads/writes.
    assert await rc.get_redis() is None
    await cache.set("k1", {"v": 1}, ttl=60)
    assert await cache.get("k1") == {"v": 1}
    await cache.delete("k1")
    assert await cache.get("k1") is None


async def test_locks_fallback_mutual_exclusion_single_process():
    token = await locks.acquire("job", 30)
    assert token is not None
    # Second acquire of the same lock is refused while held.
    assert await locks.acquire("job", 30) is None
    assert await locks.release("job", token) is True
    # After release it can be acquired again.
    assert await locks.acquire("job", 30) is not None


# --- Redis auto-reconnect -----------------------------------------------------


async def test_redis_auto_reconnect_after_outage(monkeypatch):
    monkeypatch.setattr(settings, "REDIS_URL", "redis://unused:6379/0")
    rc.set_redis_client(None)

    # Outage: build fails -> unavailable + cooldown latched.
    monkeypatch.setattr(rc, "_build_client", lambda: None)
    assert await rc.get_redis() is None
    assert rc._unavailable is True

    # Recovery available but still within cooldown -> still None.
    sentinel = object()
    monkeypatch.setattr(rc, "_build_client", lambda: sentinel)
    assert await rc.get_redis() is None

    # Cooldown elapses -> re-probe succeeds (auto-reconnect, no restart).
    rc._retry_after = 0.0
    assert await rc.get_redis() is sentinel


# --- Circuit breaker ----------------------------------------------------------


async def test_circuit_breaker_opens_and_recovers():
    from app.resilience import CircuitBreakerOpen, CircuitState, get_circuit_breaker
    from app.resilience.circuit_breaker import reset_all

    reset_all()
    cb = get_circuit_breaker("dep", failure_threshold=2, reset_timeout=0.05)

    async def boom():
        raise ValueError("down")

    async def ok():
        return 42

    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(boom)
    assert cb.state == CircuitState.OPEN

    # Fails fast while open (does not call through).
    with pytest.raises(CircuitBreakerOpen):
        await cb.call(ok)

    await asyncio.sleep(0.06)  # reset timeout elapses -> half-open trial allowed
    assert await cb.call(ok) == 42
    assert cb.state == CircuitState.CLOSED


async def test_circuit_breaker_reopens_on_half_open_failure():
    from app.resilience import CircuitState, get_circuit_breaker
    from app.resilience.circuit_breaker import reset_all

    reset_all()
    cb = get_circuit_breaker("dep2", failure_threshold=1, reset_timeout=0.05)

    async def boom():
        raise RuntimeError("still down")

    with pytest.raises(RuntimeError):
        await cb.call(boom)
    assert cb.state == CircuitState.OPEN
    await asyncio.sleep(0.06)
    with pytest.raises(RuntimeError):
        await cb.call(boom)  # half-open trial fails -> reopen
    assert cb.state == CircuitState.OPEN


# --- Bulkhead -----------------------------------------------------------------


async def test_bulkhead_rejects_when_full():
    from app.resilience import BulkheadFull, get_bulkhead
    from app.resilience.bulkhead import reset_all

    reset_all()
    bh = get_bulkhead("pool", max_concurrency=1)

    async with bh.slot():
        assert bh.active == 1
        with pytest.raises(BulkheadFull):
            async with bh.slot(wait=False):
                pass
    assert bh.active == 0


# --- Leader election ----------------------------------------------------------


async def test_leader_election_single_winner_and_renewal():
    from app.redis.locks import LeaderElector, renew

    e1 = LeaderElector("scheduler", ttl_seconds=30)
    e2 = LeaderElector("scheduler", ttl_seconds=30)

    assert await e1.try_acquire() is True
    assert e1.is_leader is True
    # A second contender cannot become leader while the lease is held.
    assert await e2.try_acquire() is False
    assert e2.is_leader is False
    # The leader can renew its own lease.
    assert await renew(e1.name, e1._token, 30) is True


# --- Versioned cache invalidation --------------------------------------------


async def test_versioned_cache_invalidation():
    await cache.versioned_set("ns", "key", value={"a": 1}, ttl=60)
    assert await cache.versioned_get("ns", "key") == {"a": 1}
    # Bumping the namespace version invalidates everything under it in O(1).
    await cache.invalidate("ns")
    assert await cache.versioned_get("ns", "key") is None


# --- Queue priority routing + delayed jobs -----------------------------------


def test_queue_priority_routing():
    from app.jobs.submit import (
        PRIORITY_DEFAULT,
        PRIORITY_HIGH,
        PRIORITY_LOW,
        queue_for_priority,
    )

    assert queue_for_priority(PRIORITY_HIGH) == settings.JOB_QUEUE_NAME_HIGH
    assert queue_for_priority(PRIORITY_LOW) == settings.JOB_QUEUE_NAME_LOW
    assert queue_for_priority(PRIORITY_DEFAULT) == settings.JOB_QUEUE_NAME


async def test_with_timeout_enforces_deadline():
    from app.resilience import with_timeout

    with pytest.raises(asyncio.TimeoutError):
        await with_timeout(asyncio.sleep(1.0), 0.01)
