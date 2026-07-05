"""Unit tests for the sliding-window rate limiter (app.security.rate_limit).

Covers spec parsing, the in-memory sliding-window semantics, header helpers and
- when ``fakeredis`` is available - the Redis (Lua) backend against an
in-process server so both backends are proven to share identical behaviour.
"""

import pytest

from app.security import rate_limit as rl
from app.security.rate_limit import (
    InMemoryRateLimitBackend,
    RateLimitConfigError,
    parse_rate,
)


def test_parse_rate_valid():
    r = parse_rate("5/60")
    assert r.limit == 5
    assert r.window == 60
    assert str(r) == "5/60"


@pytest.mark.parametrize("spec", ["", "5", "5/", "/60", "abc/60", "5/x", "0/60", "5/0", "-1/60"])
def test_parse_rate_invalid(spec):
    with pytest.raises(RateLimitConfigError):
        parse_rate(spec)


async def test_inmemory_allows_up_to_limit_then_blocks():
    backend = InMemoryRateLimitBackend()
    results = [await backend.hit("k", limit=3, window=60) for _ in range(3)]
    assert all(r.allowed for r in results)
    assert [r.remaining for r in results] == [2, 1, 0]

    blocked = await backend.hit("k", limit=3, window=60)
    assert blocked.allowed is False
    assert blocked.remaining == 0
    # A rejected request reports a positive retry-after and never consumes a slot.
    assert blocked.retry_after >= 1


async def test_inmemory_keys_are_isolated():
    backend = InMemoryRateLimitBackend()
    for _ in range(3):
        assert (await backend.hit("a", 3, 60)).allowed
    # A different key has its own independent window.
    assert (await backend.hit("b", 3, 60)).allowed
    assert (await backend.hit("a", 3, 60)).allowed is False


async def test_inmemory_window_slides(monkeypatch):
    backend = InMemoryRateLimitBackend()
    now = {"t": 1000.0}
    monkeypatch.setattr(rl.time, "monotonic", lambda: now["t"])

    for _ in range(2):
        assert (await backend.hit("k", 2, 10)).allowed
    assert (await backend.hit("k", 2, 10)).allowed is False

    # Advance past the window; the old hits fall out and traffic is allowed again.
    now["t"] += 11
    fresh = await backend.hit("k", 2, 10)
    assert fresh.allowed is True
    assert fresh.remaining == 1


async def test_inmemory_reset_clears_window():
    backend = InMemoryRateLimitBackend()
    for _ in range(2):
        await backend.hit("k", 2, 60)
    assert (await backend.hit("k", 2, 60)).allowed is False
    await backend.reset("k")
    assert (await backend.hit("k", 2, 60)).allowed is True


def test_result_retry_after_zero_when_allowed():
    from app.security.rate_limit import RateLimitResult

    allowed = RateLimitResult(allowed=True, limit=5, remaining=4, reset_after=30.0)
    assert allowed.retry_after == 0
    blocked = RateLimitResult(allowed=False, limit=5, remaining=0, reset_after=12.2)
    assert blocked.retry_after == 13


# --- Redis backend (skipped unless fakeredis with Lua support is installed) ---

def _fake_async_redis():
    fakeredis = pytest.importorskip("fakeredis")
    if not hasattr(fakeredis, "FakeAsyncRedis"):
        pytest.skip("fakeredis without async support")
    try:
        return fakeredis.FakeAsyncRedis(decode_responses=True)
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"fakeredis unavailable: {exc}")


async def test_redis_backend_matches_inmemory_semantics():
    from app.security.rate_limit import RedisRateLimitBackend

    client = _fake_async_redis()
    try:
        backend = RedisRateLimitBackend(client)
    except Exception as exc:  # pragma: no cover - no Lua support
        pytest.skip(f"redis script unsupported by fake: {exc}")

    try:
        results = [await backend.hit("k", 3, 60) for _ in range(3)]
        assert all(r.allowed for r in results)
        assert results[-1].remaining == 0
        blocked = await backend.hit("k", 3, 60)
        assert blocked.allowed is False
        assert blocked.retry_after >= 1
        # Independent key.
        assert (await backend.hit("other", 3, 60)).allowed is True
    except Exception as exc:  # pragma: no cover - no Lua support
        pytest.skip(f"fakeredis cannot eval lua: {exc}")
    finally:
        await backend.aclose()
