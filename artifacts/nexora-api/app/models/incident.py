"""Sprint 40A — Incident Investigation Engine.

Additive, customer-facing models that let an AI Team agent investigate a
production incident by reading from multiple connected, read-only tools
(Sprint 39B/39C) and producing a Root Cause Analysis report.

Strictly investigation-only: no remediation, deployments, mutations, or
autonomous actions. These tables only record what was *read* and the analysis
that was synthesized from it. They never store secrets.
"""

import enum

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDMixin


class IncidentInvestigationStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class IncidentLifecycleStatus(str, enum.Enum):
    """Sprint 58A.4 — the production incident lifecycle (distinct from the RCA
    job ``IncidentInvestigationStatus``). Every transition is validated."""

    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    INVESTIGATING = "INVESTIGATING"
    MITIGATING = "MITIGATING"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class IncidentSource(str, enum.Enum):
    """Sprint 42A — how an incident investigation was created."""

    MANUAL = "MANUAL"
    MONITORING = "MONITORING"


class MonitoringSeverity(str, enum.Enum):
    """Sprint 42A — normalized severity of an ingested monitoring alert."""

    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class MonitoringAlertStatus(str, enum.Enum):
    """Sprint 42A — lifecycle of an ingested monitoring alert."""

    FIRING = "FIRING"
    RESOLVED = "RESOLVED"


class IncidentInvestigationStepStatus(str, enum.Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class IncidentEventSeverity(str, enum.Enum):
    """Sprint 40B — normalized severity for a correlated timeline event."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class IncidentInvestigation(Base, UUIDMixin, TimestampMixin):
    """A single incident investigation session and its synthesized RCA report."""

    __tablename__ = "incident_investigations"

    # Hot list path: an org's incidents filtered by status, newest first.
    __table_args__ = (
        Index(
            "ix_incident_investigations_org_status_created",
            "organization_id",
            "status",
            "created_at",
        ),
    )

    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The AI Team / agent that performed the investigation (read-only context).
    team_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("ai_teams.id", ondelete="SET NULL"), nullable=True, index=True
    )
    agent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("ai_team_agents.id", ondelete="SET NULL"), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=IncidentInvestigationStatus.RUNNING.value
    )
    # Synthesized RCA report (customer-safe text; never secrets).
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendations: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Sprint 40B — alert correlation results (computed from the timeline).
    confidence_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    suspected_trigger: Mapped[str | None] = mapped_column(Text, nullable=True)
    suspected_provider: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Sprint 42A — provenance for proactively auto-created incidents. "MANUAL"
    # for human-opened investigations, "MONITORING" when created by the
    # continuous monitoring engine from a firing alert. severity mirrors the
    # triggering alert severity (INFO/WARNING/HIGH/CRITICAL) when monitoring-born.
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default=IncidentSource.MANUAL.value, server_default="MANUAL"
    )
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Sprint 58A.4 — production incident lifecycle (validated state machine,
    # separate from the RCA job ``status`` above). Defaults OPEN on creation.
    lifecycle_status: Mapped[str] = mapped_column(
        String(20), nullable=False,
        default=IncidentLifecycleStatus.OPEN.value, server_default="OPEN", index=True,
    )
    assignee_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    acknowledged_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IncidentInvestigationStep(Base, UUIDMixin, TimestampMixin):
    """One read-only tool action executed during an investigation (timeline entry)."""

    __tablename__ = "incident_investigation_steps"

    investigation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("incident_investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tool_provider: Mapped[str] = mapped_column(String(40), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=IncidentInvestigationStepStatus.COMPLETED.value
    )
    # Customer-safe read-only result summary (never raw secrets/credentials).
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class IncidentTimelineEvent(Base, UUIDMixin, TimestampMixin):
    """Sprint 40B — a normalized, read-only event on the incident timeline.

    Provider events (deployments, rollouts, pod restarts, metric spikes, alerts,
    incidents, …) are collected read-only and normalized into a single
    chronological series used for change correlation and confidence scoring.
    Never stores secrets — only customer-safe titles/descriptions/metadata.
    """

    __tablename__ = "incident_timeline_events"

    investigation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("incident_investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    event_timestamp: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default=IncidentEventSeverity.INFO.value
    )
    # Customer-safe structured context only (offsets, counts) — never secrets.
    # Attribute is ``event_metadata`` because ``metadata`` is reserved on the
    # SQLAlchemy declarative Base; the DB column is named ``metadata`` per spec.
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)


class DeploymentChangeEvent(Base, UUIDMixin, TimestampMixin):
    """Sprint 40C — a normalized, read-only deployment/change event.

    Captures *what changed*, *when*, *who*, and *which version* across Git
    commits/PRs/releases, CI/CD runs, Kubernetes rollouts, Azure revisions, and
    AWS ECS/EKS deployments, so the engine can correlate the change that most
    likely triggered an incident. Read-only and customer-safe — never stores
    secrets, tokens, or credentials.
    """

    __tablename__ = "deployment_change_events"

    investigation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("incident_investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    change_type: Mapped[str] = mapped_column(String(60), nullable=False)
    change_timestamp: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    actor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)


class RemediationRiskLevel(str, enum.Enum):
    """Sprint 41A — risk of acting on a remediation recommendation."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RemediationActionStatus(str, enum.Enum):
    """Sprint 41B — lifecycle of an approval-gated remediation action.

    Sprint 58A.4 adds ``PAUSED`` (a pending action temporarily held from
    approval) so the full control set — approve / reject / retry / override /
    pause / resume — can be expressed.
    """

    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    PAUSED = "PAUSED"


class RemediationApprovalStatus(str, enum.Enum):
    """Sprint 41B — a human approval decision on a remediation action."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class IncidentRecommendation(Base, UUIDMixin, TimestampMixin):
    """Sprint 41A — a ranked, recommendation-only remediation suggestion.

    Generated from the RCA, timeline (40B), change intelligence (40C), and tool
    evidence. This is advisory only — the platform never executes, deploys,
    rolls back, or mutates anything. Customer-safe text only; no secrets.
    """

    __tablename__ = "incident_recommendations"

    investigation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("incident_investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Category: Deployment / Kubernetes / Infrastructure / Application / Monitoring.
    recommendation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_level: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RemediationRiskLevel.LOW.value
    )
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_recovery_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recommendation_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)


class IncidentRemediationAction(Base, UUIDMixin, TimestampMixin):
    """Sprint 41B — an executable remediation action gated behind human approval.

    Generated from a Sprint 41A recommendation. It stays PENDING_APPROVAL until a
    human explicitly approves it; only then may it execute. The platform never
    auto-remediates or self-heals. Customer-safe text only; no secrets.
    """

    __tablename__ = "incident_remediation_actions"

    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    investigation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("incident_investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recommendation_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("incident_recommendations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action_type: Mapped[str] = mapped_column(String(60), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_level: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RemediationRiskLevel.HIGH.value
    )
    # Sprint 41C — binding to real target infrastructure. An action cannot
    # execute until it is bound to a customer credential + known target.
    # The credential itself stays encrypted in deployment_credentials; only the
    # id is referenced here. target_config holds non-secret execution params.
    credential_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("deployment_credentials.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    environment: Mapped[str | None] = mapped_column(String(80), nullable=True)
    namespace: Mapped[str | None] = mapped_column(String(160), nullable=True)
    application: Mapped[str | None] = mapped_column(String(200), nullable=True)
    target_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RemediationActionStatus.PENDING_APPROVAL.value
    )
    approved_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Customer-safe execution parameters only (e.g. target revision) — never secrets.
    action_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)


class IncidentRemediationApproval(Base, UUIDMixin, TimestampMixin):
    """Sprint 41B — a recorded human approval/rejection decision for an action."""

    __tablename__ = "incident_remediation_approvals"

    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("incident_remediation_actions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    approver_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RemediationApprovalStatus.PENDING.value
    )
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)


class MonitoringAlert(Base, UUIDMixin, TimestampMixin):
    """Sprint 42A — a normalized, deduplicated monitoring alert.

    Ingested read-only from connected monitoring providers (Prometheus, Grafana,
    Datadog, AWS CloudWatch, Azure Monitor). Repeated firings of the same logical
    alert within the dedup window are collapsed onto a single row by incrementing
    ``occurrence_count`` rather than creating a new incident — preventing alert
    storms. Critical/high alerts auto-create an ``IncidentInvestigation`` linked
    via ``incident_id``. Customer-safe metadata only; never stores secrets.
    """

    __tablename__ = "monitoring_alerts"

    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    # The provider's own alert identifier (customer-safe; not a secret).
    alert_id: Mapped[str] = mapped_column(String(200), nullable=False)
    alert_name: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default=MonitoringSeverity.WARNING.value
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=MonitoringAlertStatus.FIRING.value
    )
    service: Mapped[str | None] = mapped_column(String(200), nullable=True)
    environment: Mapped[str | None] = mapped_column(String(80), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_seen_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    incident_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("incident_investigations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Sprint 58A.3 — richer normalized ingestion fields (customer-safe metadata).
    resource: Mapped[str | None] = mapped_column(String(512), nullable=True)
    region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    labels: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    annotations: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Correlation key groups related firings (storm protection + topology view).
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # Stable hash of (org, provider, alert_name, service, environment). Backs the
    # partial-unique index that makes dedup atomic: at most one FIRING row per
    # logical alert identity, so concurrent ingests cannot create duplicates.
    dedup_key: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index(
            "uq_monitoring_alerts_active_dedup",
            "organization_id",
            "dedup_key",
            unique=True,
            sqlite_where=text("status = 'FIRING' AND dedup_key IS NOT NULL"),
            postgresql_where=text("status = 'FIRING' AND dedup_key IS NOT NULL"),
        ),
        # Hot list path: alerts for an org filtered by status, newest first.
        Index(
            "ix_monitoring_alerts_org_status_created",
            "organization_id",
            "status",
            "created_at",
        ),
    )
