"""Prometheus / OTel metrics provider."""

from __future__ import annotations

from app.observability_platform.providers.metrics_live import discover_prometheus, query_prometheus


def query(config: dict, promql: str, *, window: str = "1h") -> dict:
    return query_prometheus(config, promql, window=window)


def discover(config: dict) -> list[dict]:
    live = discover_prometheus(config)
    if live:
        return live
    return [
        {"name": "http_requests_total", "type": "counter", "labels": ["method", "status"]},
        {"name": "http_request_duration_seconds", "type": "histogram", "labels": ["method"]},
        {"name": "container_cpu_usage_seconds_total", "type": "counter", "labels": ["pod", "namespace"]},
        {"name": "container_memory_working_set_bytes", "type": "gauge", "labels": ["pod", "namespace"]},
        {"name": "kube_pod_status_phase", "type": "gauge", "labels": ["phase", "namespace"]},
    ]
