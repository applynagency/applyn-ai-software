"""Short-lived OIDC login state (CSRF + nonce + PKCE) backed by the cache layer.

The ``state`` parameter ties an authorization request to its callback. We store
the originating connection, the ``nonce`` (replay protection for the ID token)
and the PKCE ``code_verifier`` keyed by ``state`` with a short TTL, then consume
(read-and-delete) it exactly once on callback.
"""

from __future__ import annotations

import secrets

from app.core.config import settings
from app.redis import cache

_PREFIX = "sso:state:"


async def create_state(connection_id: str, nonce: str, code_verifier: str | None) -> str:
    state = secrets.token_urlsafe(32)
    await cache.set(
        f"{_PREFIX}{state}",
        {
            "connection_id": connection_id,
            "nonce": nonce,
            "code_verifier": code_verifier,
        },
        ttl=settings.SSO_STATE_TTL_SECONDS,
    )
    return state


async def consume_state(state: str) -> dict | None:
    """Return the stored record for ``state`` and invalidate it (single use)."""
    if not state:
        return None
    key = f"{_PREFIX}{state}"
    record = await cache.get(key)
    if record is not None:
        await cache.delete(key)
    return record


def new_nonce() -> str:
    return secrets.token_urlsafe(24)
