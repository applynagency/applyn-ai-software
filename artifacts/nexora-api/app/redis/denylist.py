"""JWT access-token denylist (real logout / session revocation).

Access tokens are stateless, so a logout cannot invalidate an already-issued
token on its own. This denylist records the token's ``jti`` until its natural
expiry; ``get_current_user`` rejects any token whose ``jti`` is listed.

Redis-backed when configured (shared across replicas); otherwise a process-local
dict with TTL expiry.
"""

from __future__ import annotations

import logging
import time

from app.redis import client as redis_client

logger = logging.getLogger(__name__)

# Process-local fallback: jti -> expire_at_epoch
_fallback: dict[str, float] = {}


def _k(jti: str) -> str:
    return redis_client.key("denylist", jti)


def _prune_fallback() -> None:
    now = time.time()
    for jti in [j for j, exp in _fallback.items() if exp <= now]:
        _fallback.pop(jti, None)


async def revoke(jti: str, ttl_seconds: int) -> None:
    """Add ``jti`` to the denylist for ``ttl_seconds`` (its remaining lifetime)."""
    if not jti:
        return
    ttl = max(1, int(ttl_seconds))
    client = await redis_client.get_redis()
    if client is not None:
        async with redis_client.timed("set"):
            await client.set(_k(jti), "1", ex=ttl)
    else:
        _fallback[jti] = time.time() + ttl
    try:
        from app.observability import metrics

        metrics.record_token_revocation()
    except Exception:  # pragma: no cover - metrics optional
        pass


async def is_revoked(jti: str) -> bool:
    if not jti:
        return False
    client = await redis_client.get_redis()
    if client is not None:
        async with redis_client.timed("exists"):
            return bool(await client.exists(_k(jti)))
    _prune_fallback()
    return jti in _fallback


def clear_fallback() -> None:
    """Clear the in-process fallback store (used by tests)."""
    _fallback.clear()
