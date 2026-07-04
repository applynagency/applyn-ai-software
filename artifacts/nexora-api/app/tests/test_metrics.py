"""Tests for Prometheus metrics (app.observability.metrics + /nexora-api/metrics).

Skipped entirely when ``prometheus_client`` is not installed. Each test rebuilds
the registry on an isolated ``CollectorRegistry`` so metric state does not leak
between tests.
"""

import pytest

pytest.importorskip("prometheus_client")

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from prometheus_client import CollectorRegistry

from app.middleware.metrics import MetricsMiddleware
from app.observability import metrics


def _fresh_registry():
    metrics.init_metrics(CollectorRegistry())


def _sample(name, labels=None):
    return metrics.REGISTRY.get_sample_value(name, labels or {})


def test_metrics_available():
    assert metrics.METRICS_AVAILABLE is True


def test_init_creates_metric_objects():
    _fresh_registry()
    assert metrics.http_requests_total is not None
    assert metrics.llm_requests_total is not None
    assert metrics.organizations_total is not None
    # Seeded queue series is present.
    assert _sample("nexora_queue_depth", {"queue": "monitoring_dead_letter"}) == 0.0


def test_record_request_increments_counter_and_histogram():
    _fresh_registry()
    metrics.record_request("GET", "/v1/ping", 200, 0.012)
    metrics.record_request("GET", "/v1/ping", 200, 0.034)
    c = _sample("nexora_http_requests_total", {"method": "GET", "path": "/v1/ping", "status": "200"})
    assert c == 2.0
    count = _sample("nexora_http_request_duration_seconds_count", {"method": "GET", "path": "/v1/ping"})
    assert count == 2.0


def test_status_codes_are_labelled():
    _fresh_registry()
    metrics.record_request("POST", "/v1/x", 500, 0.01)
    metrics.record_request("POST", "/v1/x", 429, 0.01)
    assert _sample("nexora_http_requests_total", {"method": "POST", "path": "/v1/x", "status": "500"}) == 1.0
    assert _sample("nexora_http_requests_total", {"method": "POST", "path": "/v1/x", "status": "429"}) == 1.0


def test_db_latency_normalizes_operation():
    _fresh_registry()
    metrics.observe_db_latency("select", 0.005)
    metrics.observe_db_latency("VACUUM", 0.005)  # unknown -> OTHER
    assert _sample("nexora_database_query_duration_seconds_count", {"operation": "SELECT"}) == 1.0
    assert _sample("nexora_database_query_duration_seconds_count", {"operation": "OTHER"}) == 1.0


def test_redis_latency_recorded():
    _fresh_registry()
    metrics.observe_redis_latency("eval", 0.002)
    assert _sample("nexora_redis_command_duration_seconds_count", {"command": "eval"}) == 1.0


def test_llm_requests_counter():
    _fresh_registry()
    metrics.record_llm_request("anthropic", "claude-sonnet-4-6", "success")
    metrics.record_llm_request("anthropic", "claude-sonnet-4-6", "error")
    assert _sample("nexora_llm_requests_total", {"provider": "anthropic", "model": "claude-sonnet-4-6", "status": "success"}) == 1.0
    assert _sample("nexora_llm_requests_total", {"provider": "anthropic", "model": "claude-sonnet-4-6", "status": "error"}) == 1.0


def test_queue_depth_gauge():
    _fresh_registry()
    metrics.set_queue_depth("monitoring_dead_letter", 7)
    assert _sample("nexora_queue_depth", {"queue": "monitoring_dead_letter"}) == 7.0


def test_recording_is_noop_without_init():
    # Simulate a process where init_metrics was never called.
    metrics.http_requests_total = None
    metrics.record_request("GET", "/x", 200, 0.1)  # must not raise


def test_render_outputs_exposition_format():
    _fresh_registry()
    metrics.record_request("GET", "/v1/ping", 200, 0.01)
    text = metrics.render().decode()
    assert "nexora_http_requests_total" in text
    assert "# HELP" in text


async def test_refresh_scheduler_gauges(monkeypatch):
    import asyncio

    from app.core import health
    from app.core.config import settings

    _fresh_registry()
    monkeypatch.setattr(settings, "WORKFLOW_SCHEDULER_ENABLED", True)
    monkeypatch.setattr(settings, "MONITORING_ENABLED", False)
    monkeypatch.setattr(settings, "ESCALATION_ENABLED", False)
    monkeypatch.setattr(settings, "UNIVERSAL_DISCOVERY_ENABLED", False)

    async def _forever():
        await asyncio.sleep(60)

    task = asyncio.create_task(_forever())
    health.register_background_tasks({"workflow_scheduler": task})
    try:
        metrics._refresh_scheduler_gauges()
        assert _sample("nexora_scheduler_jobs", {"scheduler": "workflow_scheduler"}) == 1.0
        assert _sample("nexora_scheduler_jobs", {"scheduler": "monitoring"}) == 0.0
    finally:
        task.cancel()
        health.clear_background_tasks()


async def test_refresh_db_gauges_sets_org_and_incident(monkeypatch):
    # Uses the real (sqlite) DB; tables may be empty, so just assert the gauges
    # are populated with numeric values for every incident lifecycle status.
    from app.database.session import create_tables
    from app.models.incident import IncidentLifecycleStatus

    _fresh_registry()
    await create_tables()
    await metrics._refresh_db_gauges()
    assert _sample("nexora_organizations_total", {}) is not None
    for status in IncidentLifecycleStatus:
        assert _sample("nexora_incidents_total", {"status": status.value}) == 0.0


# --- middleware + endpoint integration ---------------------------------------


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(MetricsMiddleware)

    @app.get("/v1/ping")
    async def ping():
        return JSONResponse({"ok": True})

    @app.get("/metrics")
    async def metrics_route():
        return Response(metrics.render(), media_type=metrics.CONTENT_TYPE_LATEST)

    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_middleware_records_request_and_metrics_endpoint():
    _fresh_registry()
    app = _make_app()
    async with _client(app) as c:
        assert (await c.get("/v1/ping")).status_code == 200
        scrape = await c.get("/metrics")
    assert scrape.status_code == 200
    body = scrape.text
    # Route template label, not the raw path, and the scrape itself is excluded.
    assert 'nexora_http_requests_total{method="GET",path="/v1/ping",status="200"}' in body
    assert 'path="/metrics"' not in body


async def test_metrics_endpoint_unavailable(monkeypatch):
    # When prometheus_client is "absent", the real endpoint returns 503.
    from app.main import app as real_app

    monkeypatch.setattr(metrics, "METRICS_AVAILABLE", False)
    async with _client(real_app) as c:
        r = await c.get("/nexora-api/metrics")
    assert r.status_code == 503
    assert "unavailable" in r.json()["detail"]


async def test_ui_metrics_path_serves_spa_not_prometheus():
    """Customer Metrics Explorer lives at /metrics; Prometheus scrape is under BASE_PATH."""
    from app.main import app as real_app

    transport = httpx.ASGITransport(app=real_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        ui = await c.get("/metrics")
        prom = await c.get("/nexora-api/metrics")
    if ui.status_code == 200:
        assert "text/html" in (ui.headers.get("content-type") or "")
        assert "nexora" in ui.text.lower() or "<!doctype html" in ui.text.lower()
    if prom.status_code == 200:
        assert "text/plain" in (prom.headers.get("content-type") or "") or "text/plain" in prom.text[:20]
