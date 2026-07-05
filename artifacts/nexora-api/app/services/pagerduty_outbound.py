"""PagerDuty outbound paging (Events API v2 + REST acknowledge)."""

from __future__ import annotations

import uuid

import httpx


async def trigger_event(
    routing_key: str,
    *,
    summary: str,
    severity: str = "error",
    source: str = "nexora",
    custom_details: dict | None = None,
) -> dict:
    """Create a PagerDuty incident via Events API v2."""
    if not routing_key:
        return {"sent": False, "reason": "missing_routing_key"}
    payload = {
        "routing_key": routing_key,
        "event_action": "trigger",
        "dedup_key": str(uuid.uuid4()),
        "payload": {
            "summary": summary[:1024],
            "severity": _pd_severity(severity),
            "source": source,
            "custom_details": custom_details or {},
        },
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post("https://events.pagerduty.com/v2/enqueue", json=payload)
        if resp.status_code >= 400:
            return {"sent": False, "reason": f"HTTP {resp.status_code}", "body": resp.text[:200]}
        data = resp.json()
        return {
            "sent": True,
            "dedup_key": data.get("dedup_key"),
            "message": data.get("message"),
            "status": data.get("status"),
        }


async def acknowledge_incident(api_key: str, incident_id: str) -> dict:
    """Acknowledge an open PagerDuty incident via REST API."""
    if not api_key or not incident_id:
        return {"acked": False, "reason": "missing_api_key_or_incident_id"}
    headers = {
        "Authorization": f"Token token={api_key}",
        "Accept": "application/vnd.pagerduty+json;version=2",
        "Content-Type": "application/json",
    }
    body = {"type": "incident_reference", "status": "acknowledged"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.put(
            f"https://api.pagerduty.com/incidents/{incident_id}",
            headers=headers,
            json=body,
        )
        if resp.status_code >= 400:
            return {"acked": False, "reason": f"HTTP {resp.status_code}", "body": resp.text[:200]}
        return {"acked": True, "incident_id": incident_id}


def _pd_severity(severity: str) -> str:
    s = (severity or "").upper()
    if s in ("CRITICAL", "SEV1", "P1"):
        return "critical"
    if s in ("HIGH", "WARNING", "SEV2", "P2"):
        return "error"
    if s in ("LOW", "INFO", "P3"):
        return "info"
    return "error"
