"""Cross-worker pub/sub over Redis, with a graceful no-op fallback.

A single-process deployment (and the test suite) needs no broker at all: the
connection manager already delivers to every local socket. The broker only adds
*cross-worker* delivery — when Redis is configured, an event broadcast on one
worker reaches sockets connected to other workers.

Every published envelope carries an ``origin`` (this process id) so a worker can
ignore the echo of its own publishes when it receives them back over Redis.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

from app.core.config import settings
from app.core.logging import get_logger
from app.redis.client import get_redis

logger = get_logger(__name__)

# Stable per-process id used to drop self-echoes from the Redis fan-out.
ORIGIN = uuid.uuid4().hex


def _channel(room_id: str) -> str:
    return f"{settings.WAR_ROOM_PUBSUB_PREFIX}:{room_id}"


async def publish(room_id: str, event: dict) -> bool:
    """Publish an event to other workers. Returns False when Redis is absent."""
    client = await get_redis()
    if client is None:
        return False
    try:
        await client.publish(_channel(room_id), json.dumps({"origin": ORIGIN, "event": event}))
        return True
    except Exception as exc:  # noqa: BLE001 - broadcast must never break the request
        logger.warning("warroom_broker_publish_failed", error=str(exc))
        return False


async def subscribe(room_id: str) -> AsyncIterator[dict]:
    """Yield events published by *other* workers for ``room_id``.

    Yields nothing (returns immediately) when Redis is unavailable.
    """
    client = await get_redis()
    if client is None:
        return
    pubsub = client.pubsub()
    await pubsub.subscribe(_channel(room_id))
    try:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            try:
                envelope = json.loads(message["data"])
            except (ValueError, TypeError):
                continue
            if envelope.get("origin") == ORIGIN:
                continue  # ignore our own echo
            event = envelope.get("event")
            if event is not None:
                yield event
    finally:
        try:
            await pubsub.unsubscribe(_channel(room_id))
            await pubsub.aclose()
        except Exception:  # pragma: no cover - best effort cleanup
            pass
