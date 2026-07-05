"""Shared types for the DevOps & SRE workspace."""

from __future__ import annotations

import enum


class QueueItemType(str, enum.Enum):
    INCIDENT = "INCIDENT"
    ALERT = "ALERT"
    DEPLOYMENT = "DEPLOYMENT"
    RUNBOOK = "RUNBOOK"
    APPROVAL = "APPROVAL"
    INVESTIGATION = "INVESTIGATION"
    FAILED_JOB = "FAILED_JOB"
    FAILED_WORKFLOW = "FAILED_WORKFLOW"
    GITOPS_DRIFT = "GITOPS_DRIFT"
    DRIFT = "DRIFT"
    COMPLIANCE = "COMPLIANCE"
    AI_RECOMMENDATION = "AI_RECOMMENDATION"


class QueuePriority(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class MaintenanceKind(str, enum.Enum):
    WINDOW = "WINDOW"
    FREEZE = "FREEZE"
    CLUSTER_UPGRADE = "CLUSTER_UPGRADE"
    NODE_UPGRADE = "NODE_UPGRADE"
    CERTIFICATE_ROTATION = "CERTIFICATE_ROTATION"
    PLANNED_OUTAGE = "PLANNED_OUTAGE"


class MaintenanceStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class CalendarEventKind(str, enum.Enum):
    DEPLOYMENT = "DEPLOYMENT"
    MAINTENANCE = "MAINTENANCE"
    RELEASE = "RELEASE"
    FREEZE = "FREEZE"
    INCIDENT_REVIEW = "INCIDENT_REVIEW"
    POSTMORTEM = "POSTMORTEM"
    CAPACITY = "CAPACITY"


class AutomationSuggestionKind(str, enum.Enum):
    WORKFLOW = "WORKFLOW"
    RUNBOOK = "RUNBOOK"
    POLICY = "POLICY"
    AI_AGENT = "AI_AGENT"
    AUTOMATION = "AUTOMATION"
