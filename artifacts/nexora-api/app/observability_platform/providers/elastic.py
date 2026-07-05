"""Elasticsearch log search provider."""

from __future__ import annotations

from app.observability_platform.providers.logs_live import search_elastic


def search(config: dict, *, query: str, limit: int = 100) -> dict:
    return search_elastic(config, query=query, limit=limit)
