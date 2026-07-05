"""Communications hub — templates and update generation (Sprint 65C)."""

from __future__ import annotations

DEFAULT_TEMPLATES: dict[str, dict] = {
    "incident_update_internal": {
        "kind": "INTERNAL",
        "subject": "[{severity}] {title} — internal update",
        "body": "Status: {status}\nImpact: {impact}\nNext update: {next_update}",
    },
    "incident_status_customer": {
        "kind": "CUSTOMER",
        "subject": "Service status update — {title}",
        "body": "We are investigating an issue affecting {services}. Current status: {status}.",
    },
    "incident_executive_brief": {
        "kind": "EXECUTIVE",
        "subject": "Major incident brief — {title}",
        "body": "Severity: {severity}\nBusiness impact: {impact}\nETA: {eta}",
    },
    "incident_engineering": {
        "kind": "ENGINEERING",
        "subject": "Engineering update — {title}",
        "body": "Root cause hypothesis: {root_cause}\nMitigation: {mitigation}",
    },
}


def render_template(template_key: str, context: dict) -> dict:
    tpl = DEFAULT_TEMPLATES.get(template_key, DEFAULT_TEMPLATES["incident_update_internal"])
    subject = tpl["subject"].format(**{**_defaults(), **context})
    body = tpl["body"].format(**{**_defaults(), **context})
    return {"kind": tpl["kind"], "subject": subject, "body": body, "template_key": template_key}


def _defaults() -> dict:
    return {
        "severity": "MEDIUM", "title": "Incident", "status": "Investigating",
        "impact": "Under assessment", "services": "affected services",
        "next_update": "30 minutes", "eta": "TBD", "root_cause": "Under investigation",
        "mitigation": "In progress",
    }
