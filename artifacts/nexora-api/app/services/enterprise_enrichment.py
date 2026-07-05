"""Enterprise connector enrichment — CMDB, log indexes, issue stats, scoped mutations."""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any

from urllib.parse import quote

from app.delivery.pipelines.ci_http import bearer_header, get_json


def _http_get_json(url: str, *, headers: dict | None = None, auth: tuple[str, str] | None = None) -> dict | list:
    hdrs = dict(headers or {})
    if auth:
        import base64
        raw = f"{auth[0]}:{auth[1]}".encode()
        hdrs["Authorization"] = f"Basic {base64.b64encode(raw).decode()}"
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=20.0) as resp:  # noqa: S310
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:200] if exc.fp else ""
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Unreachable: {exc.reason}") from exc


def servicenow_summary(secret: dict) -> dict:
    base = (secret.get("instance_url") or "").rstrip("/")
    user = secret.get("username")
    password = secret.get("password")
    if not base or not user or not password:
        return {"available": False}
    auth = (user, password)
    incidents = _http_get_json(
        f"{base}/api/now/table/incident?sysparm_query=active=true&sysparm_limit=1",
        auth=auth,
        headers={"Accept": "application/json"},
    )
    cmdb = _http_get_json(
        f"{base}/api/now/table/cmdb_ci_service?sysparm_limit=20",
        auth=auth,
        headers={"Accept": "application/json"},
    )
    inc_rows = incidents.get("result") if isinstance(incidents, dict) else []
    ci_rows = cmdb.get("result") if isinstance(cmdb, dict) else []
    return {
        "available": True,
        "open_incidents": len(inc_rows) if isinstance(inc_rows, list) else 0,
        "cmdb_services": len(ci_rows) if isinstance(ci_rows, list) else 0,
        "sample_services": [
            r.get("name") for r in (ci_rows or [])[:5] if isinstance(r, dict) and r.get("name")
        ],
        "mutations_supported": ["acknowledge_incident", "add_work_note"],
    }


def splunk_summary(secret: dict) -> dict:
    endpoint = (secret.get("endpoint") or "").rstrip("/")
    token = secret.get("token")
    if not endpoint or not token:
        return {"available": False}
    headers = {**bearer_header(token), "Accept": "application/json"}
    indexes = _http_get_json(
        f"{endpoint}/services/data/indexes?output_mode=json&count=20",
        headers=headers,
    )
    entries = indexes.get("entry") if isinstance(indexes, dict) else []
    names = [
        (e.get("name") or (e.get("content") or {}).get("title"))
        for e in (entries or [])[:10]
        if isinstance(e, dict)
    ]
    return {
        "available": True,
        "index_count": len(entries) if isinstance(entries, list) else 0,
        "sample_indexes": [n for n in names if n],
        "mutations_supported": ["trigger_search"],
    }


def sentry_summary(secret: dict) -> dict:
    endpoint = (secret.get("endpoint") or "https://sentry.io").rstrip("/")
    token = secret.get("token")
    if not token:
        return {"available": False}
    headers = {**bearer_header(token), "Accept": "application/json"}
    orgs = _http_get_json(f"{endpoint}/api/0/organizations/", headers=headers)
    org_slug = (orgs[0] or {}).get("slug") if isinstance(orgs, list) and orgs else None
    if not org_slug:
        return {"available": True, "unresolved_issues": 0, "organizations": []}
    issues = _http_get_json(
        f"{endpoint}/api/0/organizations/{org_slug}/issues/?query=is:unresolved&limit=50",
        headers=headers,
    )
    issue_list = issues if isinstance(issues, list) else []
    return {
        "available": True,
        "organization": org_slug,
        "unresolved_issues": len(issue_list),
        "top_issues": [
            {"id": i.get("id"), "title": i.get("title"), "count": i.get("count")}
            for i in issue_list[:5]
            if isinstance(i, dict)
        ],
        "mutations_supported": ["resolve_issue", "assign_issue"],
    }


def splunk_trigger_search(secret: dict, search_name: str) -> dict:
    endpoint = (secret.get("endpoint") or "").rstrip("/")
    token = secret.get("token")
    if not endpoint or not token or not search_name:
        return {"status": "failed", "reason": "missing_credentials_or_search"}
    headers = {**bearer_header(token), "Accept": "application/json"}
    url = f"{endpoint}/services/saved/searches/{quote(search_name)}/dispatch"
    payload = json.dumps({"output_mode": "json"}).encode()
    req = urllib.request.Request(url, data=payload, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=25.0) as resp:  # noqa: S310
            data = json.loads(resp.read().decode()) if resp.length else {}
    except urllib.error.HTTPError as exc:
        return {"status": "failed", "reason": exc.read().decode(errors="replace")[:200]}
    sid = (data.get("sid") if isinstance(data, dict) else None) or ""
    return {"status": "triggered", "search": search_name, "sid": sid}


def servicenow_acknowledge_incident(secret: dict, incident_sys_id: str, *, note: str = "") -> dict:
    base = (secret.get("instance_url") or "").rstrip("/")
    user = secret.get("username")
    password = secret.get("password")
    if not base or not user or not password or not incident_sys_id:
        return {"status": "failed", "reason": "missing_credentials_or_incident"}
    body = {"work_notes": note or "Acknowledged via Nexora", "state": "2"}
    payload = json.dumps(body).encode()
    url = f"{base}/api/now/table/incident/{incident_sys_id}"
    req = urllib.request.Request(
        url, data=payload, method="PATCH",
        headers={"Accept": "application/json", "Content-Type": "application/json",
                 "Authorization": "Basic " + __import__("base64").b64encode(f"{user}:{password}".encode()).decode()},
    )
    try:
        with urllib.request.urlopen(req, timeout=20.0) as resp:  # noqa: S310
            data = json.loads(resp.read().decode()) if resp.length else {}
    except urllib.error.HTTPError as exc:
        return {"status": "failed", "reason": exc.read().decode(errors="replace")[:200]}
    result = (data.get("result") or {}) if isinstance(data, dict) else {}
    return {
        "status": "acknowledged",
        "incident_id": incident_sys_id,
        "number": result.get("number"),
    }


def sentry_resolve_issue(secret: dict, issue_id: str) -> dict:
    endpoint = (secret.get("endpoint") or "https://sentry.io").rstrip("/")
    token = secret.get("token")
    if not endpoint or not token or not issue_id:
        return {"status": "failed", "reason": "missing_credentials_or_issue"}
    url = f"{endpoint}/api/0/issues/{issue_id}/"
    payload = json.dumps({"status": "resolved"}).encode()
    req = urllib.request.Request(
        url, data=payload, method="PUT",
        headers={**bearer_header(token), "Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20.0) as resp:  # noqa: S310
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return {"status": "failed", "reason": exc.read().decode(errors="replace")[:200]}
    return {"status": "resolved", "issue_id": issue_id, "title": data.get("title")}


_SUMMARIZERS = {
    "SERVICENOW": servicenow_summary,
    "SPLUNK": splunk_summary,
    "SENTRY": sentry_summary,
}

_MUTATORS: dict[str, Any] = {
    "SERVICENOW": servicenow_acknowledge_incident,
    "SENTRY": sentry_resolve_issue,
}


def summarize_provider(integration_key: str, secret: dict) -> dict:
    fn = _SUMMARIZERS.get((integration_key or "").upper())
    if fn is None:
        return {"integration_key": integration_key, "available": False}
    try:
        data = fn(secret)
        return {"integration_key": integration_key, **data}
    except Exception as exc:  # noqa: BLE001
        return {"integration_key": integration_key, "available": False, "error": str(exc)[:200]}


async def summarize_all(secrets: dict[str, dict]) -> list[dict]:
    tasks = [
        asyncio.to_thread(summarize_provider, key, secret)
        for key, secret in secrets.items()
        if key in _SUMMARIZERS
    ]
    return await asyncio.gather(*tasks) if tasks else []


def mutate_provider(integration_key: str, secret: dict, action: str, resource_id: str, **kwargs) -> dict:
    key = (integration_key or "").upper()
    if action == "acknowledge_incident" and key == "SERVICENOW":
        return servicenow_acknowledge_incident(secret, resource_id, note=kwargs.get("note", ""))
    if action == "resolve_issue" and key == "SENTRY":
        return sentry_resolve_issue(secret, resource_id)
    if action == "trigger_search" and key == "SPLUNK":
        return splunk_trigger_search(secret, resource_id)
    return {"status": "failed", "reason": f"unsupported_action:{action}"}
