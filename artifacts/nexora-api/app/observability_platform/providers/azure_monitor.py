"""Azure Monitor provider."""

from __future__ import annotations


def query_metrics(config: dict, query: str, *, window: str = "1h") -> dict:
    return {
        "provider": "AZURE_MONITOR",
        "query": query,
        "workspace": config.get("workspace_id"),
        "series": [{"name": query, "avg": 42.0}],
        "simulated": True,
    }


def search_logs(config: dict, *, query: str, limit: int = 100) -> dict:
    return {
        "provider": "AZURE_MONITOR",
        "query": query,
        "tables": ["AppTraces", "AppExceptions"],
        "rows": [{"TimeGenerated": "2026-07-01T12:00:00Z", "Message": f"Azure log: {query[:40]}"}],
        "simulated": True,
    }
