"""Live metric query against Prometheus and Datadog."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from app.delivery.pipelines.ci_http import get_json


def _window_seconds(window: str) -> int:
    w = (window or "1h").strip().lower()
    if w.endswith("h"):
        return max(int(w[:-1] or 1), 1) * 3600
    if w.endswith("m"):
        return max(int(w[:-1] or 5), 1) * 60
    if w.endswith("d"):
        return max(int(w[:-1] or 1), 1) * 86400
    return 3600


def _empty_metrics(provider: str, query: str, *, reason: str = "", simulated: bool = True) -> dict:
    return {
        "provider": provider,
        "query": query,
        "series": [],
        "simulated": simulated,
        "unavailable_reason": reason or None,
    }


def query_prometheus(config: dict, promql: str, *, window: str = "1h") -> dict:
    endpoint = (config.get("endpoint") or config.get("url") or "").rstrip("/")
    if not endpoint:
        return _empty_metrics("PROMETHEUS", promql, reason="missing_endpoint")

    end = int(time.time())
    start = end - _window_seconds(window)
    step = max(_window_seconds(window) // 60, 15)
    url = (
        f"{endpoint}/api/v1/query_range?"
        f"query={quote(promql or 'up')}&start={start}&end={end}&step={step}"
    )
    headers = {}
    token = config.get("token") or config.get("api_token")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        data = get_json(url, headers=headers, timeout=30.0)
    except RuntimeError as exc:
        return {
            **_empty_metrics("PROMETHEUS", promql, reason=str(exc)[:200], simulated=False),
            "error": True,
        }

    series: list[dict] = []
    for item in (data.get("data") or {}).get("result") or []:
        if not isinstance(item, dict):
            continue
        metric = item.get("metric") or {}
        values = []
        for point in item.get("values") or []:
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                values.append([point[0], point[1]])
        series.append({"metric": metric, "values": values})

    return {
        "provider": "PROMETHEUS",
        "query": promql,
        "window": window,
        "endpoint": endpoint,
        "series": series,
        "total": len(series),
        "simulated": False,
    }


def discover_prometheus(config: dict) -> list[dict]:
    endpoint = (config.get("endpoint") or config.get("url") or "").rstrip("/")
    if not endpoint:
        return []
    headers = {}
    token = config.get("token") or config.get("api_token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        data = get_json(f"{endpoint}/api/v1/label/__name__/values", headers=headers, timeout=20.0)
    except RuntimeError:
        return []
    names = (data.get("data") or [])[:100]
    return [{"name": n, "type": "metric"} for n in names if isinstance(n, str)]


def query_datadog(config: dict, query: str, *, window: str = "1h") -> dict:
    api_key = config.get("api_key")
    app_key = config.get("app_key")
    site = config.get("site") or "datadoghq.com"
    if not site.startswith("http"):
        site = f"https://api.{site.strip('.')}"
    site = site.rstrip("/")
    if not api_key or not app_key:
        return _empty_metrics("DATADOG", query, reason="missing_api_or_app_key")

    end = int(datetime.now(UTC).timestamp())
    start = end - _window_seconds(window)
    q = query or "avg:system.cpu.user{*}"
    url = (
        f"{site}/api/v1/query?from={start}&to={end}&query={quote(q)}"
    )
    headers = {"DD-API-KEY": api_key, "DD-APPLICATION-KEY": app_key}
    try:
        data = get_json(url, headers=headers, timeout=30.0)
    except RuntimeError as exc:
        return {
            **_empty_metrics("DATADOG", query, reason=str(exc)[:200], simulated=False),
            "error": True,
        }

    series: list[dict] = []
    for item in (data.get("series") or [])[:50]:
        if not isinstance(item, dict):
            continue
        points = item.get("pointlist") or []
        values = [[int(p[0] / 1000), p[1]] for p in points if isinstance(p, (list, tuple)) and len(p) >= 2]
        series.append({
            "metric": {
                "metric": item.get("metric"),
                "scope": item.get("scope"),
                "tag_set": item.get("tag_set"),
            },
            "values": values,
        })

    return {
        "provider": "DATADOG",
        "query": q,
        "window": window,
        "endpoint": site,
        "series": series,
        "total": len(series),
        "simulated": False,
    }


def discover_datadog(config: dict) -> list[dict]:
    api_key = config.get("api_key")
    app_key = config.get("app_key")
    site = config.get("site") or "datadoghq.com"
    if not site.startswith("http"):
        site = f"https://api.{site.strip('.')}"
    site = site.rstrip("/")
    if not api_key or not app_key:
        return []
    headers = {"DD-API-KEY": api_key, "DD-APPLICATION-KEY": app_key}
    try:
        data = get_json(f"{site}/api/v1/metrics?from={int((datetime.now(UTC) - timedelta(hours=1)).timestamp())}", headers=headers)
    except RuntimeError:
        return []
    metrics = (data.get("metrics") or [])[:50]
    return [{"name": m, "type": "metric"} for m in metrics if isinstance(m, str)]
