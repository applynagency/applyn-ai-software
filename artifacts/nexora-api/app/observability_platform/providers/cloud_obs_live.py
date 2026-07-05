"""Live query helpers for Azure Monitor and GCP Monitoring."""

from __future__ import annotations

import json

from app.delivery.pipelines.ci_http import get_json, post_json


def _azure_headers(config: dict) -> dict | None:
    api_key = config.get("api_key") or config.get("token")
    if api_key:
        return {"X-Api-Key": api_key}
    return None


def query_azure_metrics(config: dict, query: str, *, window: str = "1h") -> dict | None:
    workspace = config.get("workspace_id")
    headers = _azure_headers(config)
    if not workspace or not headers:
        return None
    promql = query or "Heartbeat | summarize cnt=count() by Computer | top 5 by cnt"
    try:
        data = post_json(
            f"https://api.loganalytics.io/v1/workspaces/{workspace}/query",
            {"query": promql, "timespan": window},
            headers=headers,
            timeout=30.0,
        )
        tables = data.get("tables") or []
        series = []
        for table in tables[:3]:
            if not isinstance(table, dict):
                continue
            name = (table.get("name") or "result")
            rows = table.get("rows") or []
            series.append({"name": name, "rows": len(rows), "sample": rows[:3]})
        return {
            "provider": "AZURE_MONITOR",
            "query": promql,
            "workspace": workspace,
            "series": series,
            "total": len(series),
            "simulated": False,
        }
    except RuntimeError as exc:
        return {
            "provider": "AZURE_MONITOR",
            "query": promql,
            "series": [],
            "simulated": False,
            "error": True,
            "unavailable_reason": str(exc)[:200],
        }


def search_azure_logs(config: dict, *, query: str, limit: int = 100) -> dict | None:
    workspace = config.get("workspace_id")
    headers = _azure_headers(config)
    if not workspace or not headers:
        return None
    kql = query or "Heartbeat | take 10"
    try:
        data = post_json(
            f"https://api.loganalytics.io/v1/workspaces/{workspace}/query",
            {"query": kql, "max_rows": limit},
            headers=headers,
            timeout=30.0,
        )
        rows = []
        for table in data.get("tables") or []:
            cols = [c.get("name") for c in (table.get("columns") or []) if isinstance(c, dict)]
            for row in (table.get("rows") or [])[:limit]:
                rows.append(dict(zip(cols, row, strict=False)) if cols else {"value": row})
        return {
            "provider": "AZURE_MONITOR",
            "query": kql,
            "rows": rows[:limit],
            "simulated": False,
        }
    except RuntimeError as exc:
        return {
            "provider": "AZURE_MONITOR",
            "query": kql,
            "rows": [],
            "simulated": False,
            "error": True,
            "unavailable_reason": str(exc)[:200],
        }


def query_gcp_metrics(config: dict, query: str, *, window: str = "1h") -> dict | None:
    project = config.get("project_id")
    token = config.get("access_token") or config.get("api_key") or config.get("token")
    if not project or not token:
        return None
    filter_expr = query or 'metric.type="kubernetes.io/container/cpu/core_usage_time"'
    try:
        data = get_json(
            "https://monitoring.googleapis.com/v3/projects/"
            f"{project}/timeSeries?filter={filter_expr}&pageSize=10",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )
        series = []
        for item in (data.get("timeSeries") or [])[:10]:
            if not isinstance(item, dict):
                continue
            metric = item.get("metric") or {}
            series.append({
                "metric": metric.get("type") or metric.get("labels", {}).get("name", "series"),
                "points": len(item.get("points") or []),
            })
        return {
            "provider": "GCP_MONITORING",
            "query": filter_expr,
            "project": project,
            "series": series,
            "total": len(series),
            "simulated": False,
        }
    except RuntimeError as exc:
        return {
            "provider": "GCP_MONITORING",
            "query": filter_expr,
            "series": [],
            "simulated": False,
            "error": True,
            "unavailable_reason": str(exc)[:200],
        }


def search_gcp_logs(config: dict, *, query: str, limit: int = 100) -> dict | None:
    project = config.get("project_id")
    token = config.get("access_token") or config.get("api_key") or config.get("token")
    if not project or not token:
        return None
    filter_expr = query or "severity>=DEFAULT"
    body = {
        "resourceNames": [f"projects/{project}"],
        "filter": filter_expr,
        "pageSize": min(limit, 100),
    }
    try:
        data = post_json(
            f"https://logging.googleapis.com/v2/projects/{project}/entries:list",
            body,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )
        entries = []
        for entry in (data.get("entries") or [])[:limit]:
            if not isinstance(entry, dict):
                continue
            payload = entry.get("textPayload") or entry.get("jsonPayload")
            if isinstance(payload, dict):
                payload = json.dumps(payload)[:200]
            entries.append({
                "timestamp": entry.get("timestamp"),
                "textPayload": str(payload or "")[:200],
            })
        return {
            "provider": "GCP_MONITORING",
            "query": filter_expr,
            "entries": entries,
            "simulated": False,
        }
    except RuntimeError as exc:
        return {
            "provider": "GCP_MONITORING",
            "query": filter_expr,
            "entries": [],
            "simulated": False,
            "error": True,
            "unavailable_reason": str(exc)[:200],
        }
