"""Centralized timeout helper.

Wraps any awaitable with a deadline so a hung dependency cannot block a request
or worker indefinitely. Raises ``asyncio.TimeoutError`` on expiry.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class TimeoutPolicy:
    """Named deadline policy (seconds)."""

    name: str
    seconds: float


# Sensible default policies for common dependency classes.
DEFAULT_POLICIES = {
    "database": TimeoutPolicy("database", 10.0),
    "redis": TimeoutPolicy("redis", 2.0),
    "http": TimeoutPolicy("http", 15.0),
    "llm": TimeoutPolicy("llm", 60.0),
}


async def with_timeout(awaitable: Awaitable[T], seconds: float) -> T:
    """Await ``awaitable`` with a hard deadline of ``seconds``."""
    return await asyncio.wait_for(awaitable, timeout=seconds)
