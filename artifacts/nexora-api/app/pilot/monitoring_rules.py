"""Customer pilot monitoring rule validation (Sprint 67E)."""

from __future__ import annotations

from pathlib import Path

import yaml

RULES_PATH = Path(__file__).resolve().parents[2] / "deploy" / "monitoring" / "customer-pilot-alerts.yml"

REQUIRED_ALERTS = frozenset({
    "CustomerPilotSchedulerUnhealthy",
    "CustomerPilotWorkerUnhealthy",
    "CustomerPilotReminderCronStale",
    "CustomerPilotNotificationFailuresHigh",
    "CustomerPilotNotificationQueueStale",
    "CustomerPilotSupportExportFailures",
    "CustomerPilotApprovalRemindersNotRunning",
    "CustomerPilotRedisUnavailable",
    "CustomerPilotDeploymentUnhealthy",
})

REQUIRED_PROMETHEUS_METRICS = (
    "nexora_customer_pilot_scheduler_healthy",
    "nexora_customer_pilot_worker_healthy",
    "nexora_customer_pilot_notification_deliveries_total",
    "nexora_customer_pilot_notification_failures_total",
    "nexora_customer_pilot_notification_queue_oldest_seconds",
    "nexora_customer_pilot_deployment_healthy",
)

IN_APP_ONLY_NOTIFICATION_SCOPE = (
    "Approval reminders and pilot communications are delivered in-app; "
    "email delivery is not enabled in this deployment."
)


def load_customer_pilot_alert_rules(path: Path | None = None) -> dict:
    target = path or RULES_PATH
    with open(target, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def validate_customer_pilot_alert_rules(path: Path | None = None) -> dict:
    """Validate alert rule file structure and required alert names."""
    doc = load_customer_pilot_alert_rules(path)
    groups = doc.get("groups") or []
    if not groups:
        return {"valid": False, "detail": "No alert groups defined", "alerts_found": []}

    found: set[str] = set()
    for group in groups:
        for rule in group.get("rules") or []:
            name = rule.get("alert")
            if name:
                found.add(name)

    missing = sorted(REQUIRED_ALERTS - found)
    return {
        "valid": not missing,
        "detail": "All required alerts present" if not missing else f"Missing alerts: {', '.join(missing)}",
        "alerts_found": sorted(found),
        "missing_alerts": missing,
    }
