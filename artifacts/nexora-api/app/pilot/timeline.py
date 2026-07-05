"""Customer-safe pilot timeline builders (Sprint 67C)."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from typing import Any

from app.integration_readiness.evidence import redact_text
from app.pilot.customer_portal import sanitize_customer_view
from app.pilot.stages import PILOT_EXECUTION_STAGES

CUSTOMER_TIMELINE_STATUSES = frozenset({
    "PROPOSED",
    "AWAITING_CUSTOMER_APPROVAL",
    "CUSTOMER_APPROVED",
    "CUSTOMER_REJECTED",
    "AWAITING_OPERATOR_CONFIRMATION",
    "EXECUTING",
    "VERIFICATION_PENDING",
    "VERIFIED",
    "VERIFICATION_FAILED",
    "INSUFFICIENT_EVIDENCE",
    "BLOCKED",
    "CLOSEOUT_PENDING",
    "CLOSED",
    "INFO",
})

CUSTOMER_SAFE_AUDIT_ACTIONS: dict[str, tuple[str, str, str]] = {
    "customer_pilot.approval_decided": (
        "CUSTOMER_APPROVAL_DECIDED",
        "Approval decision recorded",
        "CUSTOMER_ADMIN",
    ),
    "customer_pilot.closeout_requested": (
        "CLOSEOUT_REQUESTED",
        "Closeout review requested",
        "CUSTOMER_ADMIN",
    ),
    "customer_pilot.timeline_exported": (
        "TIMELINE_EXPORTED",
        "Timeline exported",
        "CUSTOMER_ADMIN",
    ),
    "customer_pilot.communication_acknowledged": (
        "COMMUNICATION_ACKNOWLEDGED",
        "Message acknowledged",
        "CUSTOMER_ADMIN",
    ),
    "customer_pilot.comment_added": (
        "CUSTOMER_COMMENT",
        "Customer comment added",
        "CUSTOMER_ADMIN",
    ),
    "pilot.communication_sent": (
        "COMMUNICATION_SENT",
        "Pilot update sent",
        "PLATFORM_OPERATOR",
    ),
    "pilot.approval_reminder_sent": (
        "APPROVAL_REMINDER",
        "Approval reminder sent",
        "SYSTEM",
    ),
    "pilot.approval_expired": (
        "APPROVAL_EXPIRED",
        "Approval expired",
        "SYSTEM",
    ),
}

INTERNAL_AUDIT_PREFIXES = (
    "pilot.confirmation",
    "pilot.internal",
    "pilot.kubeconfig",
    "pilot.registry",
    "integration.credential",
)


def _actor_type_for_audit(action: str, default: str = "SYSTEM") -> str:
    if action in CUSTOMER_SAFE_AUDIT_ACTIONS:
        return CUSTOMER_SAFE_AUDIT_ACTIONS[action][2]
    if action.startswith("customer_pilot."):
        return "CUSTOMER_ADMIN"
    if action.startswith("pilot."):
        return "PLATFORM_OPERATOR"
    return default


def _is_internal_audit(action: str) -> bool:
    if any(action.startswith(p) for p in INTERNAL_AUDIT_PREFIXES):
        return True
    if action in CUSTOMER_SAFE_AUDIT_ACTIONS:
        return False
    if action.startswith(("customer_pilot.", "pilot.communication", "pilot.approval_reminder", "pilot.approval_expired")):
        return False
    return True


def operation_customer_status(status: str, *, verification_status: str | None = None) -> str:
    mapping = {
        "AWAITING_APPROVAL": "AWAITING_CUSTOMER_APPROVAL",
        "PENDING_CONFIRMATION": "AWAITING_OPERATOR_CONFIRMATION",
        "EXECUTING": "EXECUTING",
        "PENDING_VERIFICATION": "VERIFICATION_PENDING",
        "SUCCEEDED": "VERIFICATION_PENDING",
        "FAILED": "BLOCKED",
        "CANCELLED": "BLOCKED",
    }
    if verification_status == "VERIFIED":
        return "VERIFIED"
    if verification_status == "VERIFICATION_FAILED":
        return "VERIFICATION_FAILED"
    if verification_status == "INSUFFICIENT_EVIDENCE":
        return "INSUFFICIENT_EVIDENCE"
    return mapping.get(status, "PROPOSED")


def build_timeline_event(
    *,
    event_id: str,
    timestamp: datetime,
    event_type: str,
    title: str,
    description: str,
    status: str,
    actor_type: str,
    metadata: dict | None = None,
    deep_link: str | None = None,
    operation_id: str | None = None,
) -> dict[str, Any]:
    ts = timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return sanitize_customer_view({
        "id": event_id,
        "timestamp": ts.isoformat(),
        "event_type": event_type,
        "title": redact_text(title),
        "description": redact_text(description),
        "status": status,
        "actor_type": actor_type,
        "metadata": metadata or {},
        "deep_link": deep_link,
        "operation_id": operation_id,
    })


def encode_cursor(timestamp: datetime, event_id: str) -> str:
    ts = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=UTC)
    payload = json.dumps({"t": ts.isoformat(), "id": event_id}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    pad = "=" * (-len(cursor) % 4)
    data = json.loads(base64.urlsafe_b64decode(cursor + pad).decode())
    ts = datetime.fromisoformat(data["t"])
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts, data["id"]


def timeline_markdown(events: list[dict], *, organization_name: str = "Organization") -> str:
    lines = [
        f"# Customer Pilot Timeline — {organization_name}",
        "",
        f"Generated at {datetime.now(UTC).isoformat()}",
        "",
    ]
    for ev in events:
        lines.append(f"## {ev.get('title', 'Event')} — {ev.get('timestamp', '')}")
        lines.append(f"- **Type:** {ev.get('event_type')}")
        lines.append(f"- **Status:** {ev.get('status')}")
        lines.append(f"- **Actor:** {ev.get('actor_type')}")
        lines.append(f"- {ev.get('description', '')}")
        lines.append("")
    return "\n".join(lines)


def timeline_html(events: list[dict], *, organization_name: str = "Organization") -> str:
    rows = "".join(
        f"<tr><td>{ev.get('timestamp','')}</td><td>{ev.get('event_type','')}</td>"
        f"<td>{ev.get('title','')}</td><td>{ev.get('status','')}</td>"
        f"<td>{ev.get('actor_type','')}</td></tr>"
        for ev in events
    )
    return (
        f"<html><body><h1>Customer Pilot Timeline — {organization_name}</h1>"
        f"<table border='1' cellpadding='4'><thead><tr>"
        f"<th>Time</th><th>Type</th><th>Title</th><th>Status</th><th>Actor</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></body></html>"
    )


def stage_summary_rows(stage_map: dict) -> list[dict]:
    rows = []
    for stage in PILOT_EXECUTION_STAGES:
        key = stage["key"]
        s = stage_map.get(key)
        rows.append({
            "stage_key": key,
            "title": stage["title"],
            "status": s.status if s else "PENDING",
            "outcome": s.outcome if s else None,
            "completed_at": s.completed_at.isoformat() if s and s.completed_at else None,
        })
    return rows
