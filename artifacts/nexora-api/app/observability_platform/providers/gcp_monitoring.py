"""Google Cloud Monitoring provider."""

from __future__ import annotations


def query_metrics(config: dict, query: str, *, window: str = "1h") -> dict:
    return {
        "provider": "GCP_MONITORING",
        "query": query,
        "project": config.get("project_id"),
        "series": [{"metric": query, "value": 55.0}],
        "simulated": True,
    }


def search_logs(config: dict, *, query: str, limit: int = 100) -> dict:
    return {
        "provider": "GCP_MONITORING",
        "query": query,
        "entries": [{"timestamp": "2026-07-01T12:00:00Z", "textPayload": f"GCP log: {query[:40]}"}],
        "simulated": True,
    }
