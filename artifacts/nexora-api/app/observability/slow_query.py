"""Slow-query logging + profiling (Sprint 62B).

Attaches SQLAlchemy cursor-execute hooks that log any statement slower than
``DB_SLOW_QUERY_MS`` (0 disables) together with its duration. This is the
production "where did my p99 go" signal — distinct from the Prometheus query
histogram in :mod:`app.observability.metrics`, which aggregates but does not name
the offending statement.

Idempotent and safe to call when the threshold is 0 (then it is a pure no-op).
"""

from __future__ import annotations

import time

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_installed = False


def _truncate(statement: str, limit: int = 500) -> str:
    s = " ".join((statement or "").split())
    return s if len(s) <= limit else s[:limit] + "…"


def install_slow_query_logging() -> None:
    """Install slow-query hooks on the shared engine (idempotent)."""
    global _installed
    if _installed:
        return
    threshold_ms = int(getattr(settings, "DB_SLOW_QUERY_MS", 0) or 0)
    if threshold_ms <= 0:
        return
    try:
        from sqlalchemy import event

        from app.database.session import engine

        sync_engine = engine.sync_engine

        @event.listens_for(sync_engine, "before_cursor_execute")
        def _before(conn, cursor, statement, params, context, executemany):
            conn.info["_nexora_slow_start"] = time.perf_counter()

        @event.listens_for(sync_engine, "after_cursor_execute")
        def _after(conn, cursor, statement, params, context, executemany):
            start = conn.info.pop("_nexora_slow_start", None)
            if start is None:
                return
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            if elapsed_ms >= threshold_ms:
                logger.warning(
                    "slow_query",
                    duration_ms=round(elapsed_ms, 2),
                    threshold_ms=threshold_ms,
                    statement=_truncate(statement),
                    executemany=bool(executemany),
                )

        _installed = True
        logger.info("slow_query_logging_enabled", threshold_ms=threshold_ms)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("slow_query_logging_install_failed", error=str(exc))
