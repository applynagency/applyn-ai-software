"""Discovery scheduler.

Background loop that periodically runs Universal Discovery for every organization
that has at least one connected provider supporting discovery. Mirrors the
established monitoring-scheduler pattern (asyncio loop, own session per tick,
cancellation-aware, synthetic OWNER actor). Read-only w.r.t. customer
infrastructure.
"""

from __future__ import annotations

import asyncio

import structlog

from app.core.config import settings
from app.services.universal_discovery import UniversalDiscoveryRunner

logger = structlog.get_logger(__name__)


async def universal_discovery_loop() -> None:
    """Periodically run universal discovery across every connected integration,
    keeping discovered assets + the Platform Knowledge Graph fresh. Read-only;
    cancellation-aware; own session per tick."""
    from app.database.session import AsyncSessionLocal

    runner = UniversalDiscoveryRunner()
    interval = max(60, settings.UNIVERSAL_DISCOVERY_INTERVAL_SECONDS)
    logger.info("universal_discovery_scheduler_started", interval_seconds=interval)
    from app.observability.tracing import start_as_current_span
    from app.redis.locks import scheduler_lock

    while True:
        try:
            async with scheduler_lock("universal_discovery") as token:
                if token is not None:
                    with start_as_current_span(
                        "scheduler.universal_discovery", kind="consumer"
                    ):
                        async with AsyncSessionLocal() as session:
                            ran = await runner.run_once(session)
                            if ran:
                                logger.info(
                                    "universal_discovery_scheduler_tick",
                                    organizations_scanned=ran,
                                )
        except asyncio.CancelledError:
            logger.info("universal_discovery_scheduler_stopped")
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("universal_discovery_scheduler_tick_failed", error=str(exc))
        await asyncio.sleep(interval)
