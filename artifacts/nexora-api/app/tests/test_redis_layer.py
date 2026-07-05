"""Tests for the unified Redis integration layer (app.redis).

Each feature is exercised twice where it matters: against the in-process
fallback (no Redis configured, the default in CI) and — when ``fakeredis`` is
installed — against a real ``redis.asyncio`` client, asserting identical
semantics. Also covers the end-to-end JWT denylist (logout revokes the access
token) and the server-side session store via the auth API.
"""

import pytest

from app.redis import cache, denylist, locks, notifications, sessions
from app.redis import client as redis_client
from app.tests.conftest import auth_headers, create_authenticated_user, jwt_claims


def _fake_async_redis():
    fakeredis = pytest.importorskip("fakeredis")
    if not hasattr(fakeredis, "FakeAsyncRedis"):
        pytest.skip("fakeredis without async support")
    try:
        return fakeredis.FakeAsyncRedis(decode_responses=True)
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"fakeredis unavailable: {exc}")


# --------------------------------------------------------------- cache
async def test_cache_set_get_delete_fallback():
    assert await cache.get("missing", default="d") == "d"
    await cache.set("k", {"a": 1}, ttl=60)
    assert await cache.get("k") == {"a": 1}
    assert await cache.exists("k") is True
    await cache.delete("k")
    assert await cache.get("k") is None


async def test_cache_incr_and_get_or_set_fallback():
    assert await cache.incr("counter") == 1
    assert await cache.incr("counter", 4) == 5

    calls = {"n": 0}

    async def factory():
        calls["n"] += 1
        return [1, 2, 3]

    assert await cache.get_or_set("lazy", 60, factory) == [1, 2, 3]
    assert await cache.get_or_set("lazy", 60, factory) == [1, 2, 3]
    assert calls["n"] == 1  # second call served from cache


async def test_cache_with_fakeredis():
    redis_client.set_redis_client(_fake_async_redis())
    await cache.set("rk", {"x": 9}, ttl=60)
    assert await cache.get("rk") == {"x": 9}
    assert await cache.incr("rc", 2) == 2
    assert await cache.incr("rc", 3) == 5


# --------------------------------------------------------------- denylist
async def test_denylist_fallback():
    assert await denylist.is_revoked("jti-1") is False
    await denylist.revoke("jti-1", 60)
    assert await denylist.is_revoked("jti-1") is True
    assert await denylist.is_revoked("") is False


async def test_denylist_with_fakeredis():
    redis_client.set_redis_client(_fake_async_redis())
    await denylist.revoke("abc", 60)
    assert await denylist.is_revoked("abc") is True
    assert await denylist.is_revoked("other") is False


# --------------------------------------------------------------- sessions
async def test_session_store_fallback():
    await sessions.create(jti="j1", user_id="u1", ttl_seconds=60, ip="1.2.3.4")
    await sessions.create(jti="j2", user_id="u1", ttl_seconds=60)
    await sessions.create(jti="j3", user_id="u2", ttl_seconds=60)

    u1 = await sessions.list_for_user("u1")
    assert {s["jti"] for s in u1} == {"j1", "j2"}
    assert await sessions.get("j1") is not None

    assert await sessions.delete("j1") is True
    assert await sessions.get("j1") is None

    removed = await sessions.delete_all_for_user("u1")
    assert removed == ["j2"]
    assert await sessions.list_for_user("u1") == []


async def test_session_store_with_fakeredis():
    redis_client.set_redis_client(_fake_async_redis())
    await sessions.create(jti="ja", user_id="ux", ttl_seconds=60)
    await sessions.create(jti="jb", user_id="ux", ttl_seconds=60)
    listed = await sessions.list_for_user("ux")
    assert {s["jti"] for s in listed} == {"ja", "jb"}
    await sessions.delete("ja")
    assert {s["jti"] for s in await sessions.list_for_user("ux")} == {"jb"}


# --------------------------------------------------------------- locks
async def test_lock_mutual_exclusion_fallback():
    token = await locks.acquire("res", 60)
    assert token is not None
    # Already held -> contended.
    assert await locks.acquire("res", 60) is None
    # Wrong owner cannot release.
    assert await locks.release("res", "wrong") is False
    assert await locks.release("res", token) is True
    # Released -> acquirable again.
    assert await locks.acquire("res", 60) is not None


async def test_lock_context_manager_skips_when_held():
    held = await locks.acquire("scheduler:x", 60)
    assert held is not None
    async with locks.lock("scheduler:x", 60) as token:
        assert token is None  # someone else owns it
    await locks.release("scheduler:x", held)


async def test_lock_with_fakeredis():
    redis_client.set_redis_client(_fake_async_redis())
    token = await locks.acquire("rlock", 60)
    assert token is not None
    assert await locks.acquire("rlock", 60) is None
    assert await locks.release("rlock", token) is True
    assert await locks.acquire("rlock", 60) is not None


# --------------------------------------------------------------- notifications
async def test_notification_queue_enqueue_and_process():
    delivered: list[dict] = []

    async def handler(payload):
        delivered.append(payload)
        return True

    await notifications.enqueue({"channels": ["slack"], "text": "hi"})
    assert await notifications.depth() == 1
    assert await notifications.process_one(handler) is True
    assert await notifications.depth() == 0
    assert delivered[0]["text"] == "hi"
    # Empty queue -> nothing processed.
    assert await notifications.process_one(handler) is False


async def test_notification_queue_retries_then_drops(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "NOTIFICATION_QUEUE_MAX_ATTEMPTS", 3)

    async def failing(payload):
        return False

    await notifications.enqueue({"text": "x"})
    # First failure re-queues with attempts=1.
    await notifications.process_one(failing)
    assert await notifications.depth() == 1
    # Second failure -> attempts=2, still re-queued.
    await notifications.process_one(failing)
    assert await notifications.depth() == 1
    # Third failure -> attempts=3 == max -> dropped.
    await notifications.process_one(failing)
    assert await notifications.depth() == 0


async def test_notification_queue_with_fakeredis():
    redis_client.set_redis_client(_fake_async_redis())

    async def handler(payload):
        return True

    await notifications.enqueue({"text": "a"})
    await notifications.enqueue({"text": "b"})
    assert await notifications.depth() == 2
    assert await notifications.process_one(handler) is True
    assert await notifications.depth() == 1


# --------------------------------------------------------------- auth e2e
async def test_logout_revokes_access_token(client):
    _, tokens = await create_authenticated_user(
        client, email="revoke@example.com", username="revokeuser"
    )
    headers = auth_headers(tokens["access_token"])

    # Token works before logout.
    assert (await client.get("/v1/auth/me", headers=headers)).status_code == 200

    logout = await client.post("/v1/auth/logout", headers=headers)
    assert logout.status_code == 204

    # Same token is now denylisted -> 401.
    after = await client.get("/v1/auth/me", headers=headers)
    assert after.status_code == 401


async def test_sessions_listed_and_revocable(client):
    _, tokens = await create_authenticated_user(
        client, email="sess@example.com", username="sessuser"
    )
    headers = auth_headers(tokens["access_token"])
    current_jti = jwt_claims(tokens["access_token"])["jti"]

    listed = await client.get("/v1/auth/sessions", headers=headers)
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] >= 1
    current = [s for s in body["sessions"] if s["jti"] == current_jti]
    assert current and current[0]["current"] is True


async def test_revoke_other_sessions(client):
    # Two logins for the same user create two sessions.
    await create_authenticated_user(
        client, email="multi@example.com", username="multiuser"
    )
    first = await client.post(
        "/v1/auth/login", json={"email": "multi@example.com", "password": "password123"}
    )
    second = await client.post(
        "/v1/auth/login", json={"email": "multi@example.com", "password": "password123"}
    )
    t1 = first.json()["access_token"]
    t2 = second.json()["access_token"]

    # Revoke all sessions except the second token's.
    resp = await client.post(
        "/v1/auth/sessions/revoke-others", headers=auth_headers(t2)
    )
    assert resp.status_code == 200
    assert resp.json()["revoked"] >= 1

    # First token is now revoked; second still works.
    assert (await client.get("/v1/auth/me", headers=auth_headers(t1))).status_code == 401
    assert (await client.get("/v1/auth/me", headers=auth_headers(t2))).status_code == 200


async def test_jti_present_in_tokens():
    from app.core.security import create_access_token, decode_token

    payload = decode_token(create_access_token("user-123"))
    assert "jti" in payload and payload["jti"]
    assert payload["type"] == "access"


async def test_shared_client_disabled_without_url():
    redis_client.set_redis_client(None)
    # conftest leaves REDIS_URL unset, so the shared client resolves to None and
    # every feature falls back to its in-process implementation.
    assert await redis_client.get_redis() is None
