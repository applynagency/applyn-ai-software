"""Bulkhead: bounded-concurrency isolation.

Limits how many concurrent operations may run against a given dependency so a
slow/failing dependency cannot exhaust all workers (the "bulkhead" keeps one
flooded compartment from sinking the ship). Optionally bounds the wait queue so
callers fail fast instead of piling up.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager


class BulkheadFull(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(f"Bulkhead '{name}' is at capacity")
        self.name = name


class Bulkhead:
    def __init__(self, name: str, *, max_concurrency: int, max_queue: int = 0) -> None:
        self.name = name
        self.max_concurrency = max_concurrency
        self.max_queue = max_queue
        self._sem = asyncio.Semaphore(max_concurrency)
        self._active = 0
        self._waiting = 0

    @property
    def active(self) -> int:
        return self._active

    @asynccontextmanager
    async def slot(self, *, wait: bool = True):
        if not wait and self._sem.locked():
            raise BulkheadFull(self.name)
        if self.max_queue and self._waiting >= self.max_queue and self._sem.locked():
            raise BulkheadFull(self.name)
        self._waiting += 1
        try:
            await self._sem.acquire()
        finally:
            self._waiting -= 1
        self._active += 1
        try:
            yield
        finally:
            self._active -= 1
            self._sem.release()

    def snapshot(self) -> dict:
        return {
            "name": self.name,
            "active": self._active,
            "waiting": self._waiting,
            "max_concurrency": self.max_concurrency,
        }


_bulkheads: dict[str, Bulkhead] = {}


def get_bulkhead(name: str, *, max_concurrency: int = 10, max_queue: int = 0) -> Bulkhead:
    bh = _bulkheads.get(name)
    if bh is None:
        bh = Bulkhead(name, max_concurrency=max_concurrency, max_queue=max_queue)
        _bulkheads[name] = bh
    return bh


def all_bulkheads() -> list[Bulkhead]:
    return list(_bulkheads.values())


def reset_all() -> None:
    _bulkheads.clear()
