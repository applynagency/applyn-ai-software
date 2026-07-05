"""CloudWatch metrics and logs provider."""

from __future__ import annotations

from app.observability_platform.providers.logs_live import search_cloudwatch


def query_metrics(config: dict, query: str, *, window: str = "1h") -> dict:
    return {
        "provider": "CLOUDWATCH",
        "query": query,
        "window": window,
        "region": config.get("region", "us-east-1"),
        "datapoints": [],
        "simulated": not config.get("access_key_id"),
        "unavailable_reason": None if config.get("access_key_id") else "connect_aws_for_live_metrics",
    }


def search_logs(config: dict, *, query: str, limit: int = 100) -> dict:
    return search_cloudwatch(config, query=query, limit=limit)
