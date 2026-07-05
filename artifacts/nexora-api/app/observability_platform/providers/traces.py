"""Tempo / Jaeger / Zipkin traces provider."""

from __future__ import annotations

from app.observability_platform.providers.traces_live import search_jaeger, search_tempo


def search(config: dict, *, query: str, limit: int = 50) -> dict:
    kind = (config.get("kind") or "TEMPO").upper()
    if kind in ("JAEGER", "ZIPKIN", "OPENTELEMETRY"):
        return search_jaeger(config, query, limit=limit)
    return search_tempo(config, query, limit=limit)
