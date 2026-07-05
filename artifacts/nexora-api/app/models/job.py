"""Async job queue records (Arq-backed).

A ``Job`` row is the durable, queryable source of truth for one unit of
background work (an AI Team run, a workflow execution, a discovery/monitoring
scan, a report generation, …). Arq owns scheduling/retry in Redis; this table
mirrors lifecycle state so the API can expose status, progress, results,
retries, cancellation and a dead-letter queue without depending on Redis
retention.

Org-scoped and additive. No secrets are stored (only non-sensitive params).
"""

import enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class JobPriority(str, enum.Enum):
    HIGH = "high"
    DEFAULT = "default"
    LOW = "low"


class JobType(str, enum.Enum):
    AI_TEAM_AGENT = "AI_TEAM_AGENT"
    AI_TEAM_WORKFLOW = "AI_TEAM_WORKFLOW"
    UNIVERSAL_DISCOVERY = "UNIVERSAL_DISCOVERY"
    MONITORING_POLL = "MONITORING_POLL"
    EXECUTIVE_REPORT = "EXECUTIVE_REPORT"
    # periodic/maintenance jobs driven by the worker's cron schedule
    CRON_WORKFLOW_SCHEDULES = "CRON_WORKFLOW_SCHEDULES"
    CRON_MONITORING = "CRON_MONITORING"
    CRON_ESCALATION = "CRON_ESCALATION"
    CRON_UNIVERSAL_DISCOVERY = "CRON_UNIVERSAL_DISCOVERY"
    # commercial platform (Sprint 61C)
    CRON_QUOTA_RESET = "CRON_QUOTA_RESET"
    CRON_USAGE_AGGREGATION = "CRON_USAGE_AGGREGATION"
    CRON_LICENSE_EXPIRATION = "CRON_LICENSE_EXPIRATION"
    CRON_BILLING_LIFECYCLE = "CRON_BILLING_LIFECYCLE"
    # AI platform (Sprint 61D)
    CRON_AI_EVALUATION = "CRON_AI_EVALUATION"
    CRON_AI_MEMORY_CONSOLIDATION = "CRON_AI_MEMORY_CONSOLIDATION"
    # production hardening (Sprint 62B)
    CRON_EXECUTION_RECOVERY = "CRON_EXECUTION_RECOVERY"
    CRON_SEARCH_INDEX = "CRON_SEARCH_INDEX"
    CRON_ARCHIVE = "CRON_ARCHIVE"
    CRON_API_KEY_ROTATION = "CRON_API_KEY_ROTATION"
    CRON_AUDIT_VERIFY = "CRON_AUDIT_VERIFY"
    CRON_EVENT_DRAIN = "CRON_EVENT_DRAIN"
    CRON_REPORT_SCHEDULE = "CRON_REPORT_SCHEDULE"
    CRON_CUSTOMER_PILOT_APPROVAL_REMINDERS = "CRON_CUSTOMER_PILOT_APPROVAL_REMINDERS"
    CRON_INTEGRATION_PIPELINE_SYNC = "CRON_INTEGRATION_PIPELINE_SYNC"
    CRON_INTEGRATION_GITOPS_SYNC = "CRON_INTEGRATION_GITOPS_SYNC"
    # Platform Engineering (Sprint 64A)
    PLATFORM_ENGINEERING_IAC = "PLATFORM_ENGINEERING_IAC"
    SECURITY_REMEDIATION = "SECURITY_REMEDIATION"


class JobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    RETRYING = "RETRYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    # terminal state after retries are exhausted — the dead-letter queue
    DEAD_LETTER = "DEAD_LETTER"


# Statuses a job can no longer move out of.
TERMINAL_STATUSES = frozenset(
    {JobStatus.COMPLETED.value, JobStatus.FAILED.value,
     JobStatus.CANCELLED.value, JobStatus.DEAD_LETTER.value}
)


class Job(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "jobs"

    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    job_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=JobStatus.QUEUED.value, index=True
    )
    # The Arq job id (Redis), so the API can abort an in-flight job.
    arq_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # Non-sensitive parameters needed to (re)run the job.
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Serialized result on success.
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Progress (0..100) and a short human-readable message.
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_message: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Retry accounting.
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    # Cooperative cancellation: the API sets this; the running task observes it.
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Sprint 62B — production execution hardening.
    # Scheduling priority (maps to the high/default/low Arq queues).
    priority: Mapped[str] = mapped_column(
        String(10), nullable=False, default=JobPriority.DEFAULT.value, index=True
    )
    # Execution lease: the worker that currently owns this run and when the lease
    # expires. A stalled run (lease expired, no heartbeat) is recoverable.
    lease_owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    heartbeat_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Per-run wall-clock timeout (seconds); 0/None falls back to the global default.
    timeout_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # Recovery scan: find RUNNING jobs whose lease has expired.
        Index("ix_jobs_status_lease", "status", "lease_expires_at"),
        # Common listing: org + status ordered by recency.
        Index("ix_jobs_org_status_created", "organization_id", "status", "created_at"),
    )
