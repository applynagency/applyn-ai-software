"""Server-side session store.

Records an entry per issued access token (keyed by its ``jti``) so active
sessions can be listed and individually revoked, despite JWTs being stateless.
Pairs with :mod:`app.redis.denylist`: revoking a session denylists its ``jti``.

Redis-backed when configured (a per-jti key plus a per-user index set);
otherwise a process-local dict with TTL expiry.
"""

from __future__ import annotations

import json
import logging
import time

from app.redis import client as redis_client

logger = logging.getLogger(__name__)

# Process-local fallback: jti -> (expire_at_epoch, metadata dict)
_fallback: dict[str, tuple[float, dict]] = {}


def _session_key(jti: str) -> str:
    return redis_client.key("session", jti)


def _user_index_key(user_id: str) -> str:
    return redis_client.key("sessions", user_id)


def _prune_fallback() -> None:
    now = time.time()
    for jti in [j for j, (exp, _) in _fallback.items() if exp <= now]:
        _fallback.pop(jti, None)


async def create(
    *,
    jti: str,
    user_id: str,
    ttl_seconds: int,
    ip: str | None = None,
    user_agent: str | None = None,
    organization_id: str | None = None,
) -> dict:
    """Record an active session; returns the stored metadata."""
    now = time.time()
    meta = {
        "jti": jti,
        "user_id": user_id,
        "ip": ip,
        "user_agent": (user_agent or "")[:256] or None,
        "organization_id": organization_id,
        "created_at": now,
        "expires_at": now + ttl_seconds,
    }
    ttl = max(1, int(ttl_seconds))
    client = await redis_client.get_redis()
    if client is not None:
        async with redis_client.timed("session_create"):
            pipe = client.pipeline()
            pipe.set(_session_key(jti), json.dumps(meta), ex=ttl)
            pipe.sadd(_user_index_key(user_id), jti)
            pipe.expire(_user_index_key(user_id), ttl)
            await pipe.execute()
    else:
        _fallback[jti] = (now + ttl, meta)
    return meta


async def get(jti: str) -> dict | None:
    client = await redis_client.get_redis()
    if client is not None:
        async with redis_client.timed("get"):
            raw = await client.get(_session_key(jti))
        return json.loads(raw) if raw else None
    _prune_fallback()
    entry = _fallback.get(jti)
    return entry[1] if entry else None


async def list_for_user(user_id: str) -> list[dict]:
    """Return active sessions for a user (pruning any that have expired)."""
    client = await redis_client.get_redis()
    if client is not None:
        members = await client.smembers(_user_index_key(user_id))
        sessions: list[dict] = []
        stale: list[str] = []
        for jti in members:
            raw = await client.get(_session_key(jti))
            if raw:
                sessions.append(json.loads(raw))
            else:
                stale.append(jti)
        if stale:
            await client.srem(_user_index_key(user_id), *stale)
        sessions.sort(key=lambda s: s.get("created_at", 0), reverse=True)
        return sessions
    _prune_fallback()
    sessions = [m for _, m in _fallback.values() if m.get("user_id") == user_id]
    sessions.sort(key=lambda s: s.get("created_at", 0), reverse=True)
    return sessions


async def delete(jti: str) -> bool:
    """Remove a single session. Returns True if it existed."""
    client = await redis_client.get_redis()
    if client is not None:
        meta = await get(jti)
        async with redis_client.timed("delete"):
            removed = await client.delete(_session_key(jti))
        if meta:
            await client.srem(_user_index_key(meta["user_id"]), jti)
        return bool(removed)
    return _fallback.pop(jti, None) is not None


async def delete_all_for_user(user_id: str, *, except_jti: str | None = None) -> list[str]:
    """Remove all sessions for a user; returns the removed jtis."""
    sessions = await list_for_user(user_id)
    removed: list[str] = []
    for meta in sessions:
        jti = meta["jti"]
        if except_jti and jti == except_jti:
            continue
        await delete(jti)
        removed.append(jti)
    return removed


async def count() -> int:
    """Approximate count of active sessions (fallback store only)."""
    _prune_fallback()
    return len(_fallback)


def clear_fallback() -> None:
    """Clear the in-process fallback store (used by tests)."""
    _fallback.clear()
