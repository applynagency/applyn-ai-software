"""Azure Monitor provider."""

from __future__ import annotations

from app.observability_platform.providers.cloud_obs_live import query_azure_metrics, search_azure_logs


def query_metrics(config: dict, query: str, *, window: str = "1h") -> dict:
    live = query_azure_metrics(config, query, window=window)
    if live is not None:
        return live
    return {
        "provider": "AZURE_MONITOR",
        "query": query,
        "workspace": config.get("workspace_id"),
        "series": [{"name": query, "avg": 42.0}],
        "simulated": True,
        "unavailable_reason": "workspace_id and api_key required for live Azure Monitor queries",
    }


def search_logs(config: dict, *, query: str, limit: int = 100) -> dict:
    live = search_azure_logs(config, query=query, limit=limit)
    if live is not None:
        return live
    return {
        "provider": "AZURE_MONITOR",
        "query": query,
        "tables": ["AppTraces", "AppExceptions"],
        "rows": [{"TimeGenerated": "2026-07-01T12:00:00Z", "Message": f"Azure log: {query[:40]}"}],
        "simulated": True,
        "unavailable_reason": "workspace_id and api_key required for live Azure log search",
    }
