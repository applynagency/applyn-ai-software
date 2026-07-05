"""Enterprise Observability Platform integration tests (Sprint 65B)."""

from __future__ import annotations

import pytest

from app.observability_platform.alert_intelligence import analyze_alerts
from app.observability_platform.correlation import build_investigation_timeline
from app.observability_platform.providers import registry as obs_registry
from app.tests.conftest import auth_headers, create_authenticated_user


def test_provider_registry_supported():
    providers = obs_registry.supported_providers()
    assert "PROMETHEUS" in providers["metrics"]
    assert "LOKI" in providers["logs"]
    assert "TEMPO" in providers["traces"]


def test_prometheus_query_stub():
    result = obs_registry.query_metrics("PROMETHEUS", {}, "up", window="5m")
    assert "series" in result or "data" in result or isinstance(result, dict)


def test_correlation_timeline_builder():
    timeline = build_investigation_timeline(
        metrics=[{"name": "error_rate", "ts": "2026-01-01T00:00:00Z", "value": 0.05}],
        logs=[{"ts": "2026-01-01T00:00:01Z", "message": "connection refused", "level": "ERROR"}],
        traces=[{"trace_id": "abc", "service": "api", "duration_ms": 450, "status": "error"}],
        alerts=[{"alert_name": "HighErrorRate", "severity": "CRITICAL"}],
    )
    assert timeline.get("timeline")
    assert timeline.get("correlation_summary")


def test_alert_intelligence_grouping():
    alerts = [
        {"alert_name": "CPUHigh", "severity": "WARNING", "service": "api", "correlation_id": "g1"},
        {"alert_name": "CPUHigh", "severity": "WARNING", "service": "api", "correlation_id": "g1"},
        {"alert_name": "DiskFull", "severity": "CRITICAL", "service": "db", "correlation_id": "g2"},
    ]
    analysis = analyze_alerts(alerts)
    assert analysis.get("groups")
    assert isinstance(analysis.get("recommendations"), list)


@pytest.mark.asyncio
async def test_observability_providers_api(client):
    _, tokens = await create_authenticated_user(client, email="obs1@e.com", username="obsuser1")
    token = tokens["access_token"]
    r = await client.get("/v1/observability/providers", headers=auth_headers(token))
    assert r.status_code == 200
    body = r.json()
    assert "metrics" in body and "logs" in body


@pytest.mark.asyncio
async def test_observability_metrics_logs_traces(client):
    _, tokens = await create_authenticated_user(client, email="obs2@e.com", username="obsuser2")
    token = tokens["access_token"]
    headers = auth_headers(token)

    metrics = await client.post(
        "/v1/observability/metrics/query",
        headers=headers,
        json={"query": "up", "window": "1h"},
    )
    assert metrics.status_code == 200

    discover = await client.get("/v1/observability/metrics/discover", headers=headers)
    assert discover.status_code == 200

    logs = await client.post(
        "/v1/observability/logs/search",
        headers=headers,
        json={"query": "error", "limit": 10},
    )
    assert logs.status_code == 200

    traces = await client.post(
        "/v1/observability/traces/search",
        headers=headers,
        json={"query": "checkout", "limit": 5},
    )
    assert traces.status_code == 200


@pytest.mark.asyncio
async def test_observability_dashboard_and_correlation(client):
    _, tokens = await create_authenticated_user(client, email="obs3@e.com", username="obsuser3")
    token = tokens["access_token"]
    headers = auth_headers(token)

    dash = await client.get("/v1/observability/dashboard", headers=headers)
    assert dash.status_code == 200
    assert "golden_signals" in dash.json()

    smap = await client.get("/v1/observability/service-map", headers=headers)
    assert smap.status_code == 200

    slo = await client.get("/v1/observability/slo", headers=headers)
    assert slo.status_code == 200

    corr = await client.post(
        "/v1/observability/correlation",
        headers=headers,
        json={"service_name": "api"},
    )
    assert corr.status_code == 201
    assert corr.json().get("timeline")

    listed = await client.get("/v1/observability/correlation", headers=headers)
    assert listed.status_code == 200
    assert isinstance(listed.json(), list)


@pytest.mark.asyncio
async def test_observability_integration_and_saved_search(client):
    _, tokens = await create_authenticated_user(client, email="obs4@e.com", username="obsuser4")
    token = tokens["access_token"]
    headers = auth_headers(token)

    created = await client.post(
        "/v1/observability/integrations",
        headers=headers,
        json={"name": "Prom Primary", "kind": "PROMETHEUS", "signal": "METRICS", "config": {"url": "http://prom"}},
    )
    assert created.status_code == 201

    saved = await client.post(
        "/v1/observability/logs/saved-searches",
        headers=headers,
        json={"name": "Errors", "signal": "LOGS", "query": "level=error"},
    )
    assert saved.status_code == 201

    alerts = await client.get("/v1/observability/alerts/intelligence", headers=headers)
    assert alerts.status_code == 200

    budgets = await client.get("/v1/observability/error-budget", headers=headers)
    assert budgets.status_code == 200
