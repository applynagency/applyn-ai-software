"""Kubernetes-grade health checks and probe state.

Provides the building blocks behind the ``/livez``, ``/readyz`` and
``/startupz`` endpoints:

* **Liveness** — is the process alive and the event loop responsive? No
  dependency checks (a failed liveness probe causes a pod *restart*, so it must
  not flap on transient dependency blips).
* **Readiness** — can this replica serve traffic? Runs dependency checks. A
  failed **critical** check returns 503 (the pod is pulled from the Service);
  non-critical failures report ``degraded`` but stay in rotation.
* **Startup** — has one-time startup (table creation, master key, schedulers)
  finished? Gates liveness/readiness during slow boots.

Checks: Database (critical), Redis, Scheduler, Storage and external AI providers
(all non-critical — the API still serves when these are degraded). Each check is
time-boxed and never raises; failures are reported as structured results.
"""

from __future__ import annotations

import asyncio
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

# Process-wide probe state ----------------------------------------------------

_started_at: float = time.time()
_startup_complete: bool = False
_background_tasks: dict[str, object] = {}


def uptime_seconds() -> float:
    return time.time() - _started_at


def mark_startup_complete() -> None:
    global _startup_complete
    _startup_complete = True


def reset_startup_state() -> None:
    """Reset startup state (called on shutdown / used by tests)."""
    global _startup_complete
    _startup_complete = False


def is_startup_complete() -> bool:
    return _startup_complete


def register_background_tasks(tasks: dict[str, object]) -> None:
    """Record background task handles so the scheduler check can inspect them."""
    _background_tasks.clear()
    _background_tasks.update(tasks)


def clear_background_tasks() -> None:
    _background_tasks.clear()


# Check results ---------------------------------------------------------------

PASS = "pass"
WARN = "warn"
FAIL = "fail"


@dataclass
class CheckResult:
    name: str
    status: str  # pass | warn | fail
    critical: bool
    detail: str | None = None
    duration_ms: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


# Individual checks -----------------------------------------------------------


async def check_database(timeout: float = 3.0) -> CheckResult:
    start = time.perf_counter()
    try:
        from sqlalchemy import text

        from app.database.session import AsyncSessionLocal

        async def _probe() -> None:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))

        await asyncio.wait_for(_probe(), timeout=timeout)
        return CheckResult("database", PASS, True, "reachable", _ms(start))
    except TimeoutError:
        return CheckResult("database", FAIL, True, f"timeout after {timeout}s", _ms(start))
    except Exception as exc:
        return CheckResult("database", FAIL, True, str(exc)[:200], _ms(start))


async def check_redis(timeout: float = 2.0) -> CheckResult:
    start = time.perf_counter()
    from app.core.config import settings

    if not settings.REDIS_URL:
        return CheckResult(
            "redis", WARN, False, "not configured (in-memory fallbacks)", _ms(start)
        )
    try:
        from app.redis import client as redis_client

        shared = await redis_client.get_redis()
        if shared is None:
            return CheckResult(
                "redis", WARN, False, "client unavailable; in-memory fallback", _ms(start)
            )
        ok = await asyncio.wait_for(redis_client.ping(), timeout=timeout)
        if ok:
            return CheckResult("redis", PASS, False, "reachable", _ms(start))
        return CheckResult("redis", FAIL, False, "ping returned falsy", _ms(start))
    except TimeoutError:
        return CheckResult("redis", FAIL, False, f"timeout after {timeout}s", _ms(start))
    except Exception as exc:
        return CheckResult("redis", FAIL, False, str(exc)[:200], _ms(start))


async def check_scheduler() -> CheckResult:
    start = time.perf_counter()
    from app.core.config import settings

    # When the async job queue owns periodic work, the in-process loops are not
    # started here — scheduling lives in the separate Arq worker process.
    if settings.JOB_QUEUE_ENABLED:
        return CheckResult(
            "scheduler", PASS, False, "delegated to async job queue worker", _ms(start)
        )

    expected = {
        "workflow_scheduler": settings.WORKFLOW_SCHEDULER_ENABLED,
        "monitoring": settings.MONITORING_ENABLED,
        "escalation": settings.ESCALATION_ENABLED,
        "discovery": settings.UNIVERSAL_DISCOVERY_ENABLED,
    }
    running: list[str] = []
    disabled: list[str] = []
    problems: list[str] = []
    for name, enabled in expected.items():
        if not enabled:
            disabled.append(name)
            continue
        task = _background_tasks.get(name)
        if task is None:
            problems.append(f"{name}: not started")
            continue
        done = getattr(task, "done", None)
        if callable(done) and done():
            reason = "stopped"
            try:
                if not task.cancelled():  # type: ignore[attr-defined]
                    exc = task.exception()  # type: ignore[attr-defined]
                    if exc is not None:
                        reason = f"crashed: {type(exc).__name__}"
            except Exception:
                reason = "stopped"
            problems.append(f"{name}: {reason}")
        else:
            running.append(name)

    detail = (
        f"running={running or '-'} disabled={disabled or '-'}"
        + (f" problems={problems}" if problems else "")
    )
    if problems:
        return CheckResult("scheduler", FAIL, False, detail, _ms(start))
    return CheckResult("scheduler", PASS, False, detail, _ms(start))


def _storage_probe_dirs() -> list[Path]:
    from app.core.config import settings

    candidates: list[Path] = [
        Path(settings.LOCAL_DATA_DIR),
        Path(settings.WAR_ROOM_UPLOAD_DIR).parent,
        Path(tempfile.gettempdir()) / "nexora",
    ]
    static_dir = Path(__file__).resolve().parents[2] / "static"
    if static_dir.exists():
        candidates.append(static_dir)
    return candidates


def _storage_dir() -> Path:
    """First writable directory from the probe list (static may be read-only)."""
    last_error: Exception | None = None
    for target in _storage_probe_dirs():
        try:
            target.mkdir(parents=True, exist_ok=True)
            probe = target / f".healthcheck-{uuid.uuid4().hex}.tmp"
            probe.write_bytes(b"ok")
            probe.unlink()
            return target
        except OSError as exc:
            last_error = exc
            continue
    raise OSError(last_error or "no writable storage directory found")


async def check_storage() -> CheckResult:
    start = time.perf_counter()

    def _probe() -> str:
        return str(_storage_dir())

    try:
        path = await asyncio.to_thread(_probe)
        return CheckResult("storage", PASS, False, f"writable: {path}", _ms(start))
    except Exception as exc:
        return CheckResult("storage", FAIL, False, str(exc)[:200], _ms(start))


async def check_ai_providers() -> CheckResult:
    # Config-only by design: probes must not make billed/rate-limited external
    # calls. AI being unconfigured is non-fatal (the platform degrades to
    # deterministic/simulated responses), so this is never critical.
    start = time.perf_counter()
    from app.core.config import settings

    anthropic = bool(settings.ANTHROPIC_API_KEY)
    openai = bool(settings.OPENAI_API_KEY)
    detail = (
        f"anthropic={'configured' if anthropic else 'unconfigured'}, "
        f"openai={'configured' if openai else 'unconfigured'}"
    )
    status = PASS if (anthropic or openai) else WARN
    return CheckResult("ai_providers", status, False, detail, _ms(start))


# Aggregation -----------------------------------------------------------------

# Default readiness check set.
READINESS_CHECKS = (
    check_database,
    check_redis,
    check_scheduler,
    check_storage,
    check_ai_providers,
)


async def run_checks(checks) -> tuple[str, list[CheckResult]]:
    """Run checks concurrently and compute an overall status.

    Overall is ``fail`` if any *critical* check fails, ``degraded`` if any
    non-critical check is failing/warning, otherwise ``ok``.
    """
    results: list[CheckResult] = list(await asyncio.gather(*(c() for c in checks)))
    overall = "ok"
    for r in results:
        if r.status == FAIL and r.critical:
            return "fail", results
        if r.status in (FAIL, WARN):
            overall = "degraded"
    return overall, results
