"""Loki log search provider."""

from __future__ import annotations

from app.observability_platform.providers.logs_live import search_loki


def search(config: dict, *, query: str, limit: int = 100) -> dict:
    return search_loki(config, query=query, limit=limit)
