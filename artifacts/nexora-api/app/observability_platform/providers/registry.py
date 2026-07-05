"""Observability backend provider registry (Sprint 65B)."""

from __future__ import annotations

from app.observability_platform.providers import (
    azure_monitor,
    cloudwatch,
    datadog,
    elastic,
    gcp_monitoring,
    loki,
    prometheus,
    traces,
)


def query_metrics(kind: str, config: dict, query: str, *, window: str = "1h") -> dict:
    impl = {
        "PROMETHEUS": prometheus.query,
        "OPENTELEMETRY": prometheus.query,
        "CLOUDWATCH": cloudwatch.query_metrics,
        "AZURE_MONITOR": azure_monitor.query_metrics,
        "GCP_MONITORING": gcp_monitoring.query_metrics,
        "DATADOG": datadog.query_metrics,
        "NEW_RELIC": prometheus.query,
        "CUSTOM": prometheus.query,
    }
    fn = impl.get(kind.upper(), prometheus.query)
    return fn(config, query, window=window)


def search_logs(kind: str, config: dict, *, query: str, limit: int = 100) -> dict:
    impl = {
        "LOKI": loki.search,
        "ELASTIC": elastic.search,
        "CLOUDWATCH": cloudwatch.search_logs,
        "AZURE_MONITOR": azure_monitor.search_logs,
        "GCP_MONITORING": gcp_monitoring.search_logs,
    }
    fn = impl.get(kind.upper(), loki.search)
    return fn(config, query=query, limit=limit)


def search_traces(kind: str, config: dict, *, query: str, limit: int = 50) -> dict:
    impl = {
        "TEMPO": traces.search,
        "JAEGER": traces.search,
        "ZIPKIN": traces.search,
        "OPENTELEMETRY": traces.search,
    }
    fn = impl.get(kind.upper(), traces.search)
    return fn(config, query=query, limit=limit)


def discover_metrics(kind: str, config: dict) -> list[dict]:
    impl = {
        "PROMETHEUS": prometheus.discover,
        "OPENTELEMETRY": prometheus.discover,
        "DATADOG": datadog.discover,
        "CLOUDWATCH": lambda c: [],
        "AZURE_MONITOR": lambda c: [],
        "GCP_MONITORING": lambda c: [],
    }
    fn = impl.get(kind.upper(), prometheus.discover)
    return fn(config)


def supported_providers() -> dict:
    return {
        "metrics": ["PROMETHEUS", "OPENTELEMETRY", "CLOUDWATCH", "AZURE_MONITOR", "GCP_MONITORING", "DATADOG", "NEW_RELIC", "CUSTOM"],
        "logs": ["LOKI", "ELASTIC", "CLOUDWATCH", "AZURE_MONITOR", "GCP_MONITORING"],
        "traces": ["TEMPO", "JAEGER", "ZIPKIN", "OPENTELEMETRY"],
    }
