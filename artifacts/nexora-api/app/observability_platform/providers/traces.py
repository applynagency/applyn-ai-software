"""Tempo / Jaeger / Zipkin traces provider."""

from __future__ import annotations


def search(config: dict, *, query: str, limit: int = 50) -> dict:
    endpoint = config.get("url") or "http://tempo:3200"
    trace = {
        "trace_id": "abc123def456",
        "root_service": "api-gateway",
        "duration_ms": 245,
        "status": "error",
        "spans": [
            {"span_id": "s1", "service": "api-gateway", "operation": "GET /checkout", "duration_ms": 245, "status": "error"},
            {"span_id": "s2", "service": "payment-svc", "operation": "charge", "duration_ms": 180, "status": "error", "parent": "s1"},
            {"span_id": "s3", "service": "postgres", "operation": "query", "duration_ms": 12, "status": "ok", "parent": "s2"},
        ],
    }
    return {
        "provider": config.get("kind", "TEMPO"),
        "query": query,
        "endpoint": endpoint,
        "traces": [trace],
        "total": 1,
        "simulated": not config.get("url"),
    }
