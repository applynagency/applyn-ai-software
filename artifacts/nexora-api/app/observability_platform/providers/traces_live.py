"""Live trace search against Jaeger and Grafana Tempo."""

from __future__ import annotations

from urllib.parse import quote

from app.delivery.pipelines.ci_http import get_json


def _sample_trace(query: str, *, provider: str, endpoint: str, simulated: bool) -> dict:
    trace = {
        "trace_id": "sample-trace",
        "root_service": "api-gateway",
        "duration_ms": 245,
        "status": "error",
        "spans": [
            {"span_id": "s1", "service": "api-gateway", "operation": "GET /checkout", "duration_ms": 245, "status": "error", "start_offset_ms": 0},
            {"span_id": "s2", "service": "payment-svc", "operation": "charge", "duration_ms": 180, "status": "error", "parent": "s1", "start_offset_ms": 12},
            {"span_id": "s3", "service": "postgres", "operation": "query", "duration_ms": 12, "status": "ok", "parent": "s2", "start_offset_ms": 45},
        ],
    }
    return {
        "provider": provider,
        "query": query,
        "endpoint": endpoint,
        "traces": [trace],
        "total": 1,
        "simulated": simulated,
        "marketplace_backed": not simulated,
    }


def _parent_span_id(span: dict) -> str | None:
    for ref in span.get("references") or []:
        if isinstance(ref, dict) and ref.get("refType") == "CHILD_OF":
            return ref.get("spanID") or ref.get("spanId")
    return None


def _parse_jaeger_traces(data: dict, limit: int) -> list[dict]:
    traces: list[dict] = []
    for item in (data.get("data") or [])[:limit]:
        if not isinstance(item, dict):
            continue
        spans = item.get("spans") or []
        processes = item.get("processes") or {}
        root = spans[0] if spans else {}
        proc = processes.get(str(root.get("processID", ""))) or {}
        service = (proc.get("serviceName") or "unknown")
        trace_start_us = min((s.get("startTime") or 0) for s in spans if isinstance(s, dict)) if spans else 0
        trace_end_us = max(
            (s.get("startTime") or 0) + (s.get("duration") or 0)
            for s in spans if isinstance(s, dict)
        ) if spans else 0
        duration_us = max(trace_end_us - trace_start_us, 1)
        has_error = any(
            any(t.get("key") == "error" and t.get("value") for t in (s.get("tags") or []))
            for s in spans if isinstance(s, dict)
        )
        parsed_spans = []
        for s in spans[:40]:
            if not isinstance(s, dict):
                continue
            start_us = s.get("startTime") or trace_start_us
            parsed_spans.append({
                "span_id": s.get("spanID") or s.get("spanId"),
                "parent": _parent_span_id(s),
                "service": (processes.get(str(s.get("processID", ""))) or {}).get("serviceName", service),
                "operation": s.get("operationName") or "span",
                "duration_ms": max(int((s.get("duration") or 0) / 1000), 1),
                "start_offset_ms": max(int((start_us - trace_start_us) / 1000), 0),
                "status": "error" if any(t.get("key") == "error" for t in (s.get("tags") or [])) else "ok",
                "tags": {
                    t.get("key"): t.get("value")
                    for t in (s.get("tags") or [])
                    if isinstance(t, dict) and t.get("key")
                },
            })
        traces.append({
            "trace_id": item.get("traceID") or item.get("traceId") or "unknown",
            "root_service": service,
            "duration_ms": max(int(duration_us / 1000), 1),
            "status": "error" if has_error else "ok",
            "spans": parsed_spans,
        })
    return traces


def _jaeger_headers(config: dict) -> dict[str, str]:
    headers: dict[str, str] = {}
    token = config.get("token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_jaeger_trace(config: dict, trace_id: str) -> dict | None:
    endpoint = (config.get("url") or config.get("endpoint") or "").rstrip("/")
    if not endpoint or not trace_id:
        return None
    url = f"{endpoint}/api/traces/{quote(trace_id)}"
    try:
        data = get_json(url, headers=_jaeger_headers(config), timeout=25.0)
    except RuntimeError:
        return None
    traces = _parse_jaeger_traces(data, 1)
    return traces[0] if traces else None


def fetch_tempo_trace(config: dict, trace_id: str) -> dict | None:
    endpoint = (config.get("url") or config.get("endpoint") or "").rstrip("/")
    if not endpoint or not trace_id:
        return None
    url = f"{endpoint}/api/traces/{quote(trace_id)}"
    try:
        data = get_json(url, headers=_jaeger_headers(config), timeout=25.0)
    except RuntimeError:
        return None
    if isinstance(data, dict) and data.get("data"):
        traces = _parse_jaeger_traces(data, 1)
        return traces[0] if traces else None
    return None


def _enrich_traces(config: dict, traces: list[dict], *, provider: str) -> list[dict]:
    fetch = fetch_tempo_trace if provider == "TEMPO" else fetch_jaeger_trace
    enriched: list[dict] = []
    for trace in traces[:25]:
        tid = trace.get("trace_id")
        if tid and (not trace.get("spans") or len(trace.get("spans") or []) < 2):
            full = fetch(config, tid)
            if full:
                enriched.append(full)
                continue
        enriched.append(trace)
    return enriched


def _looks_like_trace_id(query: str) -> bool:
    q = (query or "").strip()
    return len(q) >= 16 and all(c in "0123456789abcdefABCDEF" for c in q)


def search_jaeger(config: dict, query: str, *, limit: int = 50) -> dict:
    endpoint = (config.get("url") or config.get("endpoint") or "").rstrip("/")
    if not endpoint:
        return _sample_trace(query, provider="JAEGER", endpoint="", simulated=True)

    if _looks_like_trace_id(query):
        full = fetch_jaeger_trace(config, query.strip())
        if full:
            return {
                "provider": "JAEGER",
                "query": query,
                "endpoint": endpoint,
                "traces": [full],
                "total": 1,
                "simulated": False,
                "marketplace_backed": True,
            }

    service = (query or "").strip() or "api-gateway"
    url = f"{endpoint}/api/traces?service={quote(service)}&limit={min(limit, 50)}"
    try:
        data = get_json(url, headers=_jaeger_headers(config), timeout=25.0)
    except RuntimeError:
        return _sample_trace(query, provider="JAEGER", endpoint=endpoint, simulated=True)

    traces = _enrich_traces(config, _parse_jaeger_traces(data, limit), provider="JAEGER")
    if not traces:
        return {
            "provider": "JAEGER",
            "query": query,
            "endpoint": endpoint,
            "traces": [],
            "total": 0,
            "simulated": False,
            "marketplace_backed": True,
        }
    return {
        "provider": "JAEGER",
        "query": query,
        "endpoint": endpoint,
        "traces": traces,
        "total": len(traces),
        "simulated": False,
        "marketplace_backed": True,
    }


def search_tempo(config: dict, query: str, *, limit: int = 50) -> dict:
    endpoint = (config.get("url") or config.get("endpoint") or "").rstrip("/")
    if not endpoint:
        return _sample_trace(query, provider="TEMPO", endpoint="", simulated=True)

    if _looks_like_trace_id(query):
        full = fetch_tempo_trace(config, query.strip())
        if full:
            return {
                "provider": "TEMPO",
                "query": query,
                "endpoint": endpoint,
                "traces": [full],
                "total": 1,
                "simulated": False,
                "marketplace_backed": True,
            }

    q = quote((query or "").strip() or "{}")
    url = f"{endpoint}/api/search?q={q}&limit={min(limit, 50)}"
    try:
        data = get_json(url, headers=_jaeger_headers(config), timeout=25.0)
    except RuntimeError:
        return _sample_trace(query, provider="TEMPO", endpoint=endpoint, simulated=True)

    traces = []
    for item in (data.get("traces") or [])[:limit]:
        if not isinstance(item, dict):
            continue
        traces.append({
            "trace_id": item.get("traceID") or item.get("traceId") or "unknown",
            "root_service": item.get("rootServiceName") or item.get("rootTraceName") or "service",
            "duration_ms": int(item.get("durationMs") or item.get("duration_ms") or 1),
            "status": "error" if item.get("status") == "error" else "ok",
            "spans": [],
        })
    traces = _enrich_traces(config, traces, provider="TEMPO")
    return {
        "provider": "TEMPO",
        "query": query,
        "endpoint": endpoint,
        "traces": traces,
        "total": len(traces),
        "simulated": False,
        "marketplace_backed": True,
    }
