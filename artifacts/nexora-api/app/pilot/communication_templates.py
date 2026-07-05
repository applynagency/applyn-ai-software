"""Customer-safe pilot communication templates (Sprint 67C)."""

from __future__ import annotations

PILOT_COMMUNICATION_TEMPLATES: dict[str, dict[str, str]] = {
    "PILOT_STATUS_UPDATE": {
        "title": "Pilot status update",
        "body": "Your scoped non-production pilot status has been updated. Review the latest timeline in the Customer Pilot portal.",
        "deep_link": "/customer-pilot",
    },
    "APPROVAL_REQUEST": {
        "title": "Approval required",
        "body": "A proposed pilot operation requires your review and approval before any platform operator can proceed.",
        "deep_link": "/customer-pilot/approval",
    },
    "APPROVAL_REMINDER": {
        "title": "Approval reminder",
        "body": "Your pilot operation approval is approaching its expiry window. Please review the approval package soon.",
        "deep_link": "/customer-pilot/approval",
    },
    "EXECUTION_UPDATE": {
        "title": "Execution update",
        "body": "The pilot operation execution status has changed. Customer approval does not authorize execution — platform operator confirmation is still required.",
        "deep_link": "/customer-pilot/execution",
    },
    "VERIFICATION_UPDATE": {
        "title": "Verification update",
        "body": "Post-operation verification has been updated. Review the outcome in your Customer Pilot evidence view.",
        "deep_link": "/customer-pilot/evidence",
    },
    "EVIDENCE_READY": {
        "title": "Evidence pack ready",
        "body": "A redacted evidence pack is available for your pilot operation.",
        "deep_link": "/customer-pilot/evidence",
    },
    "CLOSEOUT_UPDATE": {
        "title": "Closeout update",
        "body": "Your pilot closeout request status has been updated.",
        "deep_link": "/customer-pilot/closeout",
    },
}


def render_template(category: str, *, variables: dict[str, str] | None = None) -> dict[str, str]:
    base = PILOT_COMMUNICATION_TEMPLATES.get(category, PILOT_COMMUNICATION_TEMPLATES["PILOT_STATUS_UPDATE"])
    title = base["title"]
    body = base["body"]
    for key, value in (variables or {}).items():
        title = title.replace(f"{{{key}}}", value)
        body = body.replace(f"{{{key}}}", value)
    return {"title": title, "body": body, "deep_link": base["deep_link"]}
