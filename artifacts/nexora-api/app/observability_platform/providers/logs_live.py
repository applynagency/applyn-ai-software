"""Live log search against Loki, Elasticsearch, and CloudWatch."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from app.delivery.pipelines.ci_http import get_json


def _loki_logql(query: str) -> str:
    q = (query or "").strip()
    if not q:
        return '{job=~".+"}'
    if "{" in q and "}" in q:
        return q
    safe = q.replace('"', '\\"')
    return f'{{job=~".+"}} |= "{safe}"'


def search_loki(config: dict, *, query: str, limit: int = 100) -> dict:
    endpoint = (config.get("endpoint") or config.get("url") or "").rstrip("/")
    if not endpoint:
        return _empty_result("LOKI", query, reason="missing_endpoint")

    logql = _loki_logql(query)
    end_ns = int(time.time() * 1_000_000_000)
    start_ns = end_ns - int(timedelta(hours=1).total_seconds() * 1_000_000_000)
    url = (
        f"{endpoint}/loki/api/v1/query_range?"
        f"query={quote(logql)}&limit={min(limit, 500)}"
        f"&start={start_ns}&end={end_ns}&direction=backward"
    )
    try:
        data = get_json(url, timeout=30.0)
    except RuntimeError as exc:
        return _empty_result("LOKI", query, reason=str(exc)[:200], simulated=False, error=True)

    lines: list[dict] = []
    for stream in (data.get("data") or {}).get("result") or []:
        if not isinstance(stream, dict):
            continue
        labels = stream.get("stream") or {}
        for value in stream.get("values") or []:
            if not isinstance(value, (list, tuple)) or len(value) < 2:
                continue
            ts_raw, line = value[0], value[1]
            try:
                ts = datetime.fromtimestamp(int(ts_raw) / 1_000_000_000, tz=UTC).isoformat()
            except (TypeError, ValueError):
                ts = str(ts_raw)
            lines.append({"ts": ts, "line": str(line), "labels": labels})
            if len(lines) >= limit:
                break
        if len(lines) >= limit:
            break

    return {
        "provider": "LOKI",
        "query": query,
        "logql": logql,
        "endpoint": endpoint,
        "lines": lines,
        "total": len(lines),
        "simulated": False,
    }


def search_elastic(config: dict, *, query: str, limit: int = 100) -> dict:
    endpoint = (config.get("endpoint") or config.get("url") or "").rstrip("/")
    api_key = config.get("api_key")
    if not endpoint or not api_key:
        return _empty_result("ELASTIC", query, reason="missing_endpoint_or_api_key")

    index = config.get("index") or "logs-*"
    body = {
        "size": min(limit, 500),
        "sort": [{"@timestamp": {"order": "desc"}}],
        "query": {
            "query_string": {
                "query": query or "*",
                "default_field": "message",
            }
        },
    }
    url = f"{endpoint}/{index}/_search"
    headers = {
        "Authorization": f"ApiKey {api_key}",
        "Content-Type": "application/json",
    }
    try:
        raw = _post_json(url, body, headers=headers)
    except RuntimeError as exc:
        return _empty_result("ELASTIC", query, reason=str(exc)[:200], simulated=False, error=True)

    lines: list[dict] = []
    for hit in (raw.get("hits") or {}).get("hits") or []:
        if not isinstance(hit, dict):
            continue
        src = hit.get("_source") or {}
        ts = src.get("@timestamp") or src.get("timestamp") or hit.get("_id")
        message = src.get("message") or src.get("log") or json.dumps(src)[:2000]
        lines.append({
            "ts": str(ts) if ts else None,
            "line": str(message),
            "labels": {"index": hit.get("_index"), "id": hit.get("_id")},
        })

    return {
        "provider": "ELASTIC",
        "query": query,
        "endpoint": endpoint,
        "index": index,
        "lines": lines,
        "total": len(lines),
        "simulated": False,
    }


def search_cloudwatch(config: dict, *, query: str, limit: int = 100) -> dict:
    region = config.get("region") or "us-east-1"
    access_key = config.get("access_key_id") or config.get("access_key") or config.get("aws_access_key_id")
    secret_key = config.get("secret_access_key") or config.get("secret_key") or config.get("aws_secret_access_key")
    if not access_key or not secret_key:
        return _empty_result("CLOUDWATCH", query, reason="missing_aws_credentials")

    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError

        client = boto3.client(
            "logs",
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        log_group = config.get("log_group") or config.get("log_group_name")
        if not log_group:
            described = client.describe_log_groups(limit=1)
            groups = described.get("logGroups") or []
            if not groups:
                return _empty_result("CLOUDWATCH", query, reason="no_log_groups_found", simulated=False)
            log_group = groups[0]["logGroupName"]
        start = int((datetime.now(UTC) - timedelta(hours=1)).timestamp() * 1000)
        end = int(datetime.now(UTC).timestamp() * 1000)
        resp = client.filter_log_events(
            logGroupName=log_group,
            filterPattern=query or "",
            startTime=start,
            endTime=end,
            limit=min(limit, 500),
        )
    except (ImportError, BotoCoreError, ClientError, Exception) as exc:  # noqa: BLE001
        return _empty_result("CLOUDWATCH", query, reason=str(exc)[:200], simulated=False, error=True)

    lines = [
        {
            "ts": datetime.fromtimestamp(ev["timestamp"] / 1000, tz=UTC).isoformat(),
            "line": ev.get("message", ""),
            "labels": {"log_stream": ev.get("logStreamName")},
        }
        for ev in resp.get("events") or []
    ]
    return {
        "provider": "CLOUDWATCH",
        "query": query,
        "log_group": log_group,
        "region": region,
        "lines": lines,
        "total": len(lines),
        "simulated": False,
    }


def _post_json(url: str, body: dict, *, headers: dict | None = None, timeout: float = 30.0) -> dict:
    import urllib.error
    import urllib.request

    payload = json.dumps(body).encode()
    hdrs = dict(headers or {})
    req = urllib.request.Request(url, data=payload, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode(errors="replace")[:200] if exc.fp else ""
        raise RuntimeError(f"HTTP {exc.code}: {body_text}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Unreachable: {exc.reason}") from exc


def _empty_result(
    provider: str, query: str, *, reason: str = "", simulated: bool = True, error: bool = False,
) -> dict:
    return {
        "provider": provider,
        "query": query,
        "lines": [],
        "total": 0,
        "simulated": simulated,
        "unavailable_reason": reason or None,
        "error": error,
    }
