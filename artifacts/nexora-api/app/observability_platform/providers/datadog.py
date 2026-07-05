"""Datadog metrics provider."""

from __future__ import annotations

from app.observability_platform.providers.metrics_live import discover_datadog, query_datadog


def query_metrics(config: dict, query: str, *, window: str = "1h") -> dict:
    return query_datadog(config, query, window=window)


def discover(config: dict) -> list[dict]:
    return discover_datadog(config)
