"""Google Cloud Monitoring provider."""

from __future__ import annotations

from app.observability_platform.providers.cloud_obs_live import query_gcp_metrics, search_gcp_logs


def query_metrics(config: dict, query: str, *, window: str = "1h") -> dict:
    live = query_gcp_metrics(config, query, window=window)
    if live is not None:
        return live
    return {
        "provider": "GCP_MONITORING",
        "query": query,
        "project": config.get("project_id"),
        "series": [{"metric": query, "value": 55.0}],
        "simulated": True,
        "unavailable_reason": "project_id and access_token required for live GCP Monitoring queries",
    }


def search_logs(config: dict, *, query: str, limit: int = 100) -> dict:
    live = search_gcp_logs(config, query=query, limit=limit)
    if live is not None:
        return live
    return {
        "provider": "GCP_MONITORING",
        "query": query,
        "entries": [{"timestamp": "2026-07-01T12:00:00Z", "textPayload": f"GCP log: {query[:40]}"}],
        "simulated": True,
        "unavailable_reason": "project_id and access_token required for live GCP log search",
    }
