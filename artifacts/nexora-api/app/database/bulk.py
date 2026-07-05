"""Bulk insert + batch update helpers (Sprint 62B).

Hot write paths (usage metering, search indexing, event fan-out) should not do
one INSERT/UPDATE per row. These helpers issue chunked, set-based statements so
N rows cost O(N/chunk) round-trips instead of O(N), bounding memory and keeping
transactions short.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import insert, update
from sqlalchemy.ext.asyncio import AsyncSession


def _chunks(rows: Sequence[dict], size: int) -> Iterable[Sequence[dict]]:
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


async def bulk_insert(
    session: AsyncSession, model, rows: Sequence[dict], *, chunk_size: int = 500
) -> int:
    """Insert many rows in chunked, set-based statements. Returns row count.

    Caller is responsible for committing. Each dict must contain all
    non-defaulted columns (including ``id`` for UUID PKs without server defaults).
    """
    if not rows:
        return 0
    total = 0
    for chunk in _chunks(list(rows), max(1, chunk_size)):
        await session.execute(insert(model), list(chunk))
        total += len(chunk)
    return total


async def batch_update_by_ids(
    session: AsyncSession, model, ids: Sequence[Any], values: dict, *,
    id_attr: str = "id", chunk_size: int = 500,
) -> int:
    """Apply ``values`` to all rows whose id is in ``ids`` (chunked IN clauses)."""
    if not ids:
        return 0
    col = getattr(model, id_attr)
    total = 0
    id_list = list(ids)
    for i in range(0, len(id_list), max(1, chunk_size)):
        chunk = id_list[i:i + chunk_size]
        result = await session.execute(
            update(model).where(col.in_(chunk)).values(**values))
        total += int(result.rowcount or 0)
    return total
