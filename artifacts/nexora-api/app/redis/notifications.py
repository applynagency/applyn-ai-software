"""Outbound notification queue.

Buffers customer-safe notification payloads on a Redis list so the slow,
network-bound delivery (Slack webhook / email) happens out-of-band on a
background drainer instead of inline in the request or scheduler tick. Failed
deliveries are retried up to ``NOTIFICATION_QUEUE_MAX_ATTEMPTS`` times.

When Redis is unavailable a process-local deque provides the same API. The
queue is opt-in (``NOTIFICATION_QUEUE_ENABLED``); when disabled, producers send
inline as before.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from collections.abc import Awaitable, Callable

from app.core.config import settings
from app.redis import client as redis_client

logger = logging.getLogger(__name__)

# Process-local fallback queue. Bounded so a Redis outage cannot grow the heap
# without limit; oldest buffered notifications are dropped first (and logged).
_FALLBACK_MAXLEN = 10_000
_fallback: deque[str] = deque(maxlen=_FALLBACK_MAXLEN)


def _queue_key() -> str:
    return redis_client.key("notifications", "queue")


async def enqueue(payload: dict) -> None:
    """Append a notification payload (a dict) to the queue."""
    payload.setdefault("attempts", 0)
    raw = json.dumps(payload, default=str)
    client = await redis_client.get_redis()
    if client is not None:
        async with redis_client.timed("rpush"):
            await client.rpush(_queue_key(), raw)
    else:
        if len(_fallback) >= _FALLBACK_MAXLEN:
            logger.warning(
                "notification_fallback_full: dropping oldest (maxlen=%d)",
                _FALLBACK_MAXLEN,
            )
        _fallback.append(raw)
    await _refresh_depth_metric()


async def depth() -> int:
    client = await redis_client.get_redis()
    if client is not None:
        async with redis_client.timed("llen"):
            return int(await client.llen(_queue_key()))
    return len(_fallback)


async def _pop() -> dict | None:
    client = await redis_client.get_redis()
    raw: str | None
    if client is not None:
        async with redis_client.timed("lpop"):
            raw = await client.lpop(_queue_key())
    else:
        raw = _fallback.popleft() if _fallback else None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):  # pragma: no cover - defensive
        return None


async def _refresh_depth_metric() -> None:
    try:
        from app.observability import metrics

        metrics.set_queue_depth("notifications", await depth())
    except Exception:  # pragma: no cover - metrics optional
        pass


Handler = Callable[[dict], Awaitable[bool]]


async def process_one(handler: Handler) -> bool:
    """Pop and deliver one payload. Returns True if one was processed.

    On delivery failure the payload is re-queued with an incremented attempt
    count until ``NOTIFICATION_QUEUE_MAX_ATTEMPTS`` is reached.
    """
    payload = await _pop()
    if payload is None:
        return False
    try:
        ok = await handler(payload)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("notification_handler_error", extra={"error": str(exc)})
        ok = False
    if not ok:
        payload["attempts"] = int(payload.get("attempts", 0)) + 1
        if payload["attempts"] < settings.NOTIFICATION_QUEUE_MAX_ATTEMPTS:
            await enqueue(payload)
        else:
            logger.warning(
                "notification_dropped_max_attempts",
                extra={"attempts": payload["attempts"]},
            )
    await _refresh_depth_metric()
    return True


async def drain_loop(handler: Handler, stop_event: asyncio.Event) -> None:
    """Background loop: drain the queue until ``stop_event`` is set."""
    interval = max(1, settings.NOTIFICATION_QUEUE_POLL_SECONDS)
    logger.info("notification_drainer_started")
    while not stop_event.is_set():
        try:
            processed = await process_one(handler)
            if processed:
                continue  # keep draining while items remain
        except asyncio.CancelledError:
            logger.info("notification_drainer_stopped")
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("notification_drainer_error", extra={"error": str(exc)})
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except TimeoutError:
            pass


async def default_handler(payload: dict) -> bool:
    """Deliver an enqueued incident notification via its transport channels."""
    from app.services.incident_notifications import deliver_transport

    return await deliver_transport(payload)


def clear_fallback() -> None:
    """Clear the in-process fallback queue (used by tests)."""
    _fallback.clear()
