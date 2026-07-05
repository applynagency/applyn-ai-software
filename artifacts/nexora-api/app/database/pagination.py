"""Keyset (cursor) pagination (Sprint 62B).

OFFSET pagination degrades linearly: ``OFFSET 100000`` makes the database scan
and discard 100k rows. Keyset pagination seeks directly to the cursor position
using an indexed ordering column, so deep pages cost the same as the first page.

Designed for time-ordered listings (created_at desc, id desc tiebreaker) which
are the common case across Nexora list endpoints.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, or_, select


def encode_cursor(value: Any, tiebreaker: Any) -> str:
    raw = json.dumps({"v": _jsonable(value), "t": tiebreaker}, default=str)
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str | None) -> tuple[Any, Any] | None:
    if not cursor:
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        return data.get("v"), data.get("t")
    except Exception:
        return None


def _jsonable(value: Any) -> Any:
    iso = getattr(value, "isoformat", None)
    return iso() if callable(iso) else value


@dataclass
class Page:
    items: list[Any]
    next_cursor: str | None
    has_more: bool


async def keyset_page(
    session, model, *, order_col, id_col, limit: int = 50,
    cursor: str | None = None, base_stmt=None, descending: bool = True,
) -> Page:
    """Fetch one keyset page ordered by ``(order_col, id_col)``.

    ``base_stmt`` may carry filters (e.g. organization scoping); when omitted a
    plain ``select(model)`` is used. Returns up to ``limit`` items plus the
    cursor for the next page.
    """
    stmt = base_stmt if base_stmt is not None else select(model)
    decoded = decode_cursor(cursor)
    if decoded is not None:
        last_val, last_id = decoded
        if descending:
            stmt = stmt.where(or_(
                order_col < last_val,
                and_(order_col == last_val, id_col < last_id),
            ))
        else:
            stmt = stmt.where(or_(
                order_col > last_val,
                and_(order_col == last_val, id_col > last_id),
            ))
    order = (order_col.desc(), id_col.desc()) if descending else (order_col.asc(), id_col.asc())
    stmt = stmt.order_by(*order).limit(limit + 1)
    rows = list((await session.execute(stmt)).scalars().all())

    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = encode_cursor(getattr(last, order_col.key), getattr(last, id_col.key))
    return Page(items=items, next_cursor=next_cursor, has_more=has_more)
