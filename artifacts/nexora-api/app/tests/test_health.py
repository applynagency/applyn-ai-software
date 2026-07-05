"""Tests for Kubernetes-grade health probes (/livez, /readyz, /startupz).

Unit-tests the individual checks and aggregation in ``app.core.health`` and
integration-tests the endpoints on the real application (dependency checks are
monkeypatched where needed so failure/degraded paths are deterministic).
"""

import httpx

from app.core import health
from app.core.health import CheckResult, run_checks

# --- unit: individual checks -------------------------------------------------


async def test_check_database_passes_on_sqlite():
    # The test suite runs against sqlite in-memory, so SELECT 1 must succeed.
    r = await health.check_database()
    assert r.name == "database"
    assert r.status == health.PASS
    assert r.critical is True
    assert r.duration_ms is not None


async def test_check_redis_warns_when_unconfigured(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "REDIS_URL", None)
    r = await health.check_redis()
    assert r.status == health.WARN
    assert r.critical is False
    assert "not configured" in (r.detail or "")


async def test_check_storage_is_writable():
    r = await health.check_storage()
    assert r.name == "storage"
    assert r.status == health.PASS
    assert "writable" in (r.detail or "")


async def test_check_ai_providers_status_reflects_keys(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", None)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    r = await health.check_ai_providers()
    assert r.status == health.WARN
    assert r.critical is False

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-test")
    r2 = await health.check_ai_providers()
    assert r2.status == health.PASS
    assert "configured" in (r2.detail or "")


async def test_check_scheduler_all_disabled_passes(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "JOB_QUEUE_ENABLED", False)
    for flag in (
        "WORKFLOW_SCHEDULER_ENABLED",
        "MONITORING_ENABLED",
        "ESCALATION_ENABLED",
        "UNIVERSAL_DISCOVERY_ENABLED",
    ):
        monkeypatch.setattr(settings, flag, False)
    health.clear_background_tasks()
    r = await health.check_scheduler()
    assert r.status == health.PASS
    assert r.critical is False


async def test_check_scheduler_enabled_but_missing_fails(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "JOB_QUEUE_ENABLED", False)
    monkeypatch.setattr(settings, "WORKFLOW_SCHEDULER_ENABLED", True)
    monkeypatch.setattr(settings, "MONITORING_ENABLED", False)
    monkeypatch.setattr(settings, "ESCALATION_ENABLED", False)
    monkeypatch.setattr(settings, "UNIVERSAL_DISCOVERY_ENABLED", False)
    health.clear_background_tasks()  # task not registered
    r = await health.check_scheduler()
    assert r.status == health.FAIL
    assert r.critical is False  # scheduler outage does not pull the pod
    assert "not started" in (r.detail or "")


async def test_check_scheduler_running_task_passes(monkeypatch):
    import asyncio

    from app.core.config import settings

    monkeypatch.setattr(settings, "JOB_QUEUE_ENABLED", False)
    monkeypatch.setattr(settings, "WORKFLOW_SCHEDULER_ENABLED", True)
    monkeypatch.setattr(settings, "MONITORING_ENABLED", False)
    monkeypatch.setattr(settings, "ESCALATION_ENABLED", False)
    monkeypatch.setattr(settings, "UNIVERSAL_DISCOVERY_ENABLED", False)

    async def _forever():
        await asyncio.sleep(60)

    task = asyncio.create_task(_forever())
    health.register_background_tasks({"workflow_scheduler": task})
    try:
        r = await health.check_scheduler()
        assert r.status == health.PASS
    finally:
        task.cancel()
        health.clear_background_tasks()


# --- unit: aggregation -------------------------------------------------------


async def test_run_checks_overall_ok():
    async def a():
        return CheckResult("a", health.PASS, True)

    async def b():
        return CheckResult("b", health.PASS, False)

    overall, results = await run_checks([a, b])
    assert overall == "ok"
    assert len(results) == 2


async def test_run_checks_degraded_on_noncritical():
    async def crit():
        return CheckResult("db", health.PASS, True)

    async def soft():
        return CheckResult("redis", health.FAIL, False)

    overall, _ = await run_checks([crit, soft])
    assert overall == "degraded"


async def test_run_checks_fail_on_critical():
    async def crit():
        return CheckResult("db", health.FAIL, True)

    async def soft():
        return CheckResult("redis", health.WARN, False)

    overall, _ = await run_checks([crit, soft])
    assert overall == "fail"


# --- unit: startup gate ------------------------------------------------------


def test_startup_state_toggle():
    health.reset_startup_state()
    assert health.is_startup_complete() is False
    health.mark_startup_complete()
    assert health.is_startup_complete() is True
    health.reset_startup_state()
    assert health.is_startup_complete() is False


# --- integration: endpoints --------------------------------------------------


def _client() -> httpx.AsyncClient:
    from app.main import app

    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_livez_always_alive():
    async with _client() as c:
        r = await c.get("/livez")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "alive"
    assert "uptime_seconds" in body
    assert "version" in body


async def test_readyz_ok_when_all_pass(monkeypatch):
    async def ok(name):
        return CheckResult(name, health.PASS, name == "database")

    monkeypatch.setattr(health, "check_database", lambda: ok("database"))
    monkeypatch.setattr(health, "check_redis", lambda: ok("redis"))
    monkeypatch.setattr(health, "check_scheduler", lambda: ok("scheduler"))
    monkeypatch.setattr(health, "check_storage", lambda: ok("storage"))
    monkeypatch.setattr(health, "check_ai_providers", lambda: ok("ai_providers"))

    async with _client() as c:
        r = await c.get("/readyz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    names = {c["name"] for c in body["checks"]}
    assert names == {"database", "redis", "scheduler", "storage", "ai_providers"}


async def test_readyz_503_when_database_fails(monkeypatch):
    async def db_fail():
        return CheckResult("database", health.FAIL, True, "boom")

    async def ok(name):
        return CheckResult(name, health.PASS, False)

    monkeypatch.setattr(health, "check_database", db_fail)
    monkeypatch.setattr(health, "check_redis", lambda: ok("redis"))
    monkeypatch.setattr(health, "check_scheduler", lambda: ok("scheduler"))
    monkeypatch.setattr(health, "check_storage", lambda: ok("storage"))
    monkeypatch.setattr(health, "check_ai_providers", lambda: ok("ai_providers"))

    async with _client() as c:
        r = await c.get("/readyz")
    assert r.status_code == 503
    assert r.json()["status"] == "fail"


async def test_readyz_degraded_stays_in_rotation(monkeypatch):
    async def db_ok():
        return CheckResult("database", health.PASS, True)

    async def redis_down():
        return CheckResult("redis", health.FAIL, False, "down")

    async def ok(name):
        return CheckResult(name, health.PASS, False)

    monkeypatch.setattr(health, "check_database", db_ok)
    monkeypatch.setattr(health, "check_redis", redis_down)
    monkeypatch.setattr(health, "check_scheduler", lambda: ok("scheduler"))
    monkeypatch.setattr(health, "check_storage", lambda: ok("storage"))
    monkeypatch.setattr(health, "check_ai_providers", lambda: ok("ai_providers"))

    async with _client() as c:
        r = await c.get("/readyz")
    assert r.status_code == 200  # degraded but still ready
    assert r.json()["status"] == "degraded"


async def test_startupz_503_before_complete(monkeypatch):
    health.reset_startup_state()
    async with _client() as c:
        r = await c.get("/startupz")
    assert r.status_code == 503
    assert r.json()["status"] == "starting"


async def test_startupz_200_after_complete(monkeypatch):
    async def db_ok():
        return CheckResult("database", health.PASS, True)

    monkeypatch.setattr(health, "check_database", db_ok)
    health.mark_startup_complete()
    try:
        async with _client() as c:
            r = await c.get("/startupz")
        assert r.status_code == 200
        assert r.json()["status"] == "started"
    finally:
        health.reset_startup_state()


# --- unit: CORS configuration ------------------------------------------------


def test_cors_development_wildcard_without_credentials(monkeypatch):
    from app.core.config import settings
    from app.main import _cors_middleware_kwargs

    monkeypatch.setattr(settings, "CORS_ALLOWED_ORIGINS", [])
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    kwargs = _cors_middleware_kwargs()
    assert kwargs["allow_origins"] == ["*"]
    assert kwargs["allow_credentials"] is False


def test_cors_production_explicit_origins(monkeypatch):
    from app.core.config import settings
    from app.main import _cors_middleware_kwargs

    monkeypatch.setattr(settings, "CORS_ALLOWED_ORIGINS", ["https://app.example.com"])
    monkeypatch.setattr(settings, "CORS_ALLOW_CREDENTIALS", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    kwargs = _cors_middleware_kwargs()
    assert kwargs["allow_origins"] == ["https://app.example.com"]
    assert kwargs["allow_credentials"] is True


def test_cors_wildcard_strips_credentials(monkeypatch):
    from app.core.config import settings
    from app.main import _cors_middleware_kwargs

    monkeypatch.setattr(settings, "CORS_ALLOWED_ORIGINS", ["*"])
    monkeypatch.setattr(settings, "CORS_ALLOW_CREDENTIALS", True)
    kwargs = _cors_middleware_kwargs()
    assert kwargs["allow_credentials"] is False
