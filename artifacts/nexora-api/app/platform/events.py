"""Unified domain event model + Redis-backed event bus (Sprint 62A).

There is exactly ONE event system in Nexora. Services publish first-class
domain events through :class:`EventBus`; everything else (activity feed,
notifications, integrations) subscribes. Events are persisted (outbox / event
store) so they can be replayed, retried, and dead-lettered.

* publish      — persist + fan-out to Redis + dispatch to in-process subscribers
* subscribe    — register async handlers per event type (or ``"*"`` wildcard)
* retries      — failed handlers leave the event ``failed`` until max attempts
* dead-letter  — exhausted events become ``dead_letter`` and can be requeued
* replay       — re-dispatch any persisted event(s) on demand
"""

from __future__ import annotations

import asyncio
import enum
import json
from collections.abc import Awaitable, Callable
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.database.base import utcnow
from app.models.platform_core import DomainEvent, EventStatus

logger = get_logger(__name__)


def _metric_event(event_type: str, status: str) -> None:
    try:
        from app.observability import metrics

        metrics.record_event(event_type, status)
    except Exception:  # pragma: no cover
        pass


def _metric_replay(mode: str) -> None:
    try:
        from app.observability import metrics

        metrics.record_event_replay(mode)
    except Exception:  # pragma: no cover
        pass

EventHandler = Callable[[AsyncSession, DomainEvent], Awaitable[None]]


class DomainEventType(str, enum.Enum):
    """First-class domain events. ``everything emits events``."""

    INCIDENT_CREATED = "IncidentCreated"
    INCIDENT_RESOLVED = "IncidentResolved"
    DEPLOYMENT_COMPLETED = "DeploymentCompleted"
    DISCOVERY_FINISHED = "DiscoveryFinished"
    WORKFLOW_COMPLETED = "WorkflowCompleted"
    USER_INVITED = "UserInvited"
    ORGANIZATION_CREATED = "OrganizationCreated"
    SUBSCRIPTION_CHANGED = "SubscriptionChanged"
    COPILOT_COMPLETED = "CopilotCompleted"
    AGENT_RUN_COMPLETED = "AgentRunCompleted"
    NOTIFICATION_SENT = "NotificationSent"
    PLUGIN_INSTALLED = "PluginInstalled"
    # Sprint 63B — DevOps delivery platform
    REPOSITORY_CONNECTED = "RepositoryConnected"
    PIPELINE_STARTED = "PipelineStarted"
    PIPELINE_COMPLETED = "PipelineCompleted"
    DEPLOYMENT_STARTED = "DeploymentStarted"
    DEPLOYMENT_SUCCEEDED = "DeploymentSucceeded"
    DEPLOYMENT_FAILED = "DeploymentFailed"
    RELEASE_CREATED = "ReleaseCreated"
    RELEASE_APPROVED = "ReleaseApproved"
    RELEASE_COMPLETED = "ReleaseCompleted"
    ARTIFACT_PUBLISHED = "ArtifactPublished"
    GITOPS_SYNC_COMPLETED = "GitOpsSyncCompleted"
    # Sprint 63C — DevOps & SRE workspace
    OPS_DAILY_BRIEFING = "OpsDailyBriefing"
    OPS_SHIFT_HANDOVER = "OpsShiftHandover"
    OPS_MAINTENANCE_SCHEDULED = "OpsMaintenanceScheduled"
    # Sprint 64A — Platform Engineering (IaC)
    ENVIRONMENT_CREATED = "EnvironmentCreated"
    PROVISION_STARTED = "ProvisionStarted"
    PROVISION_COMPLETED = "ProvisionCompleted"
    TERRAFORM_PLAN_GENERATED = "TerraformPlanGenerated"
    TERRAFORM_APPLIED = "TerraformApplied"
    TERRAFORM_DRIFT_DETECTED = "TerraformDriftDetected"
    PLATFORM_TEMPLATE_CREATED = "PlatformTemplateCreated"
    SECRET_ROTATED = "SecretRotated"
    # Sprint 64B — AI Platform Operator
    OPERATOR_RECOMMENDATION_CREATED = "OperatorRecommendationCreated"
    OPERATOR_APPROVED = "OperatorApproved"
    OPERATOR_EXECUTED = "OperatorExecuted"
    OPERATOR_LEARNING_UPDATED = "OperatorLearningUpdated"
    OPERATOR_GOAL_ACHIEVED = "OperatorGoalAchieved"
    OPERATOR_SIMULATION_COMPLETED = "OperatorSimulationCompleted"
    # Sprint 65A — Advanced Kubernetes Operations
    POD_RESTARTED = "PodRestarted"
    DEPLOYMENT_SCALED = "DeploymentScaled"
    ROLLOUT_STARTED = "RolloutStarted"
    ROLLOUT_COMPLETED = "RolloutCompleted"
    NODE_DRAINED = "NodeDrained"
    NAMESPACE_CREATED = "NamespaceCreated"
    PVC_EXPANDED = "PVCExpanded"
    NETWORK_POLICY_APPLIED = "NetworkPolicyApplied"
    DIAGNOSTICS_COLLECTED = "DiagnosticsCollected"
    # Sprint 65B — Enterprise Observability Platform
    METRIC_THRESHOLD_EXCEEDED = "MetricThresholdExceeded"
    LOG_PATTERN_DETECTED = "LogPatternDetected"
    TRACE_ANOMALY_DETECTED = "TraceAnomalyDetected"
    SLO_BREACH = "SLOBreach"
    ERROR_BUDGET_BURNING = "ErrorBudgetBurning"
    GOLDEN_SIGNAL_CHANGED = "GoldenSignalChanged"
    ALERT_CORRELATED = "AlertCorrelated"
    ROOT_CAUSE_DETECTED = "RootCauseDetected"
    # Sprint 65C — Enterprise Incident Response & On-Call Platform
    ON_CALL_STARTED = "OnCallStarted"
    ON_CALL_ENDED = "OnCallEnded"
    ESCALATION_TRIGGERED = "EscalationTriggered"
    ESCALATION_SUCCEEDED = "EscalationSucceeded"
    MAJOR_INCIDENT_STARTED = "MajorIncidentStarted"
    MAJOR_INCIDENT_ENDED = "MajorIncidentEnded"
    STATUS_PAGE_UPDATED = "StatusPageUpdated"
    POSTMORTEM_GENERATED = "PostmortemGenerated"
    RESPONDER_ASSIGNED = "ResponderAssigned"
    # Sprint 65D — Enterprise DevSecOps & Cloud Security Platform
    SECURITY_FINDING_CREATED = "SecurityFindingCreated"
    SECURITY_FINDING_UPDATED = "SecurityFindingUpdated"
    CRITICAL_VULNERABILITY_DETECTED = "CriticalVulnerabilityDetected"
    SECRET_DETECTED = "SecretDetected"
    POLICY_VIOLATION_DETECTED = "PolicyViolationDetected"
    SECURITY_SCORE_CHANGED = "SecurityScoreChanged"
    SECURITY_REMEDIATION_PROPOSED = "SecurityRemediationProposed"
    SECURITY_REMEDIATION_EXECUTED = "SecurityRemediationExecuted"
    SECURITY_EXCEPTION_GRANTED = "SecurityExceptionGranted"
    SECURITY_INCIDENT_CREATED = "SecurityIncidentCreated"
    # Sprint 65E — Security Platform production integration
    SECURITY_PROVIDER_VALIDATED = "SecurityProviderValidated"
    SECURITY_SCAN_STARTED = "SecurityScanStarted"
    SECURITY_SCAN_COMPLETED = "SecurityScanCompleted"
    SECURITY_BACKFILL_COMPLETED = "SecurityBackfillCompleted"
    SECURITY_SBOM_IMPORTED = "SecuritySBOMImported"
    SECURITY_REMEDIATION_EXECUTION_STARTED = "SecurityRemediationExecutionStarted"
    SECURITY_REMEDIATION_EXECUTION_COMPLETED = "SecurityRemediationExecutionCompleted"
    SECURITY_SLA_BREACHED = "SecuritySLABreached"
    SECURITY_GATE_BLOCKED = "SecurityGateBlocked"
    # Sprint 65F — GitOps Progressive Delivery & Release Reliability
    RELEASE_VERIFICATION_STARTED = "ReleaseVerificationStarted"
    RELEASE_VERIFICATION_PASSED = "ReleaseVerificationPassed"
    RELEASE_VERIFICATION_FAILED = "ReleaseVerificationFailed"
    HEALTH_GATE_EVALUATED = "HealthGateEvaluated"
    ROLLOUT_PROPOSED = "RolloutProposed"
    ROLLOUT_PROMOTED = "RolloutPromoted"
    ROLLOUT_PAUSED = "RolloutPaused"
    ROLLOUT_ABORTED = "RolloutAborted"
    ROLLBACK_RECOMMENDED = "RollbackRecommended"
    ROLLBACK_EXECUTED = "RollbackExecuted"
    PROMOTION_REQUESTED = "PromotionRequested"
    PROMOTION_APPROVED = "PromotionApproved"
    PROMOTION_BLOCKED = "PromotionBlocked"
    FREEZE_WINDOW_STARTED = "FreezeWindowStarted"
    FREEZE_WINDOW_ENDED = "FreezeWindowEnded"
    # Sprint 65G — Production integrations & operational readiness
    INTEGRATION_VALIDATION_STARTED = "IntegrationValidationStarted"
    INTEGRATION_CONNECTED = "IntegrationConnected"
    INTEGRATION_DEGRADED = "IntegrationDegraded"
    INTEGRATION_FAILED = "IntegrationFailed"
    INTEGRATION_RECOVERED = "IntegrationRecovered"
    INTEGRATION_EXPIRED = "IntegrationExpired"
    INTEGRATION_REAUTH_REQUIRED = "IntegrationReauthRequired"
    INTEGRATION_CAPABILITY_CHANGED = "IntegrationCapabilityChanged"
    INTEGRATION_EXPIRY_WARNING = "IntegrationExpiryWarning"
    # Sprint 67A — Customer integration onboarding
    INTEGRATION_ONBOARDING_STARTED = "IntegrationOnboardingStarted"
    INTEGRATION_CREDENTIAL_STORED = "IntegrationCredentialStored"
    INTEGRATION_VALIDATION_SUCCEEDED = "IntegrationValidationSucceeded"
    INTEGRATION_VALIDATION_FAILED = "IntegrationValidationFailed"
    INTEGRATION_SCOPE_REJECTED = "IntegrationScopeRejected"
    INTEGRATION_RBAC_GAP_DETECTED = "IntegrationRBACGapDetected"
    INTEGRATION_ONBOARDING_CANCELLED = "IntegrationOnboardingCancelled"
    CUSTOMER_PILOT_READINESS_EVALUATED = "CustomerPilotReadinessEvaluated"
    LIVE_OPERATION_BLOCKED = "LiveOperationBlocked"
    LIVE_OPERATION_EXECUTED = "LiveOperationExecuted"
    LIVE_OPERATION_VERIFIED = "LiveOperationVerified"
    # Sprint 65H — Live mutation preflight enforcement
    LIVE_OPERATION_PREFLIGHT_STARTED = "LiveOperationPreflightStarted"
    LIVE_OPERATION_PREFLIGHT_PASSED = "LiveOperationPreflightPassed"
    LIVE_OPERATION_PREFLIGHT_BLOCKED = "LiveOperationPreflightBlocked"
    LIVE_OPERATION_EXECUTION_STARTED = "LiveOperationExecutionStarted"
    LIVE_OPERATION_EXECUTION_SUCCEEDED = "LiveOperationExecutionSucceeded"
    LIVE_OPERATION_EXECUTION_FAILED = "LiveOperationExecutionFailed"
    LIVE_OPERATION_VERIFICATION_FAILED = "LiveOperationVerificationFailed"
    # Sprint 66A — Production pilot readiness
    PILOT_STARTED = "PilotStarted"
    PILOT_READINESS_CHECKED = "PilotReadinessChecked"
    PILOT_INTEGRATION_CONNECTED = "PilotIntegrationConnected"
    PILOT_ASSESSMENT_COMPLETED = "PilotAssessmentCompleted"
    PILOT_BASELINE_CAPTURED = "PilotBaselineCaptured"
    PILOT_LIVE_OPERATION_ENABLED = "PilotLiveOperationEnabled"
    PILOT_LIVE_OPERATION_CONFIRMED = "PilotLiveOperationConfirmed"
    PILOT_LIVE_OPERATION_COMPLETED = "PilotLiveOperationCompleted"
    PILOT_BLOCKED = "PilotBlocked"
    PILOT_SUPPORT_BUNDLE_GENERATED = "PilotSupportBundleGenerated"
    PILOT_COMPLETED = "PilotCompleted"
    # Sprint 67C — Customer pilot communications & timeline
    CUSTOMER_PILOT_COMMUNICATION_DRAFTED = "CustomerPilotCommunicationDrafted"
    CUSTOMER_PILOT_COMMUNICATION_SENT = "CustomerPilotCommunicationSent"
    CUSTOMER_PILOT_COMMUNICATION_ACKNOWLEDGED = "CustomerPilotCommunicationAcknowledged"
    CUSTOMER_PILOT_COMMENT_ADDED = "CustomerPilotCommentAdded"
    CUSTOMER_PILOT_APPROVAL_REMINDER_SENT = "CustomerPilotApprovalReminderSent"
    CUSTOMER_PILOT_APPROVAL_EXPIRED = "CustomerPilotApprovalExpired"
    CUSTOMER_PILOT_NOTIFICATION_PREFERENCE_UPDATED = "CustomerPilotNotificationPreferenceUpdated"
    CUSTOMER_PILOT_TIMELINE_EXPORTED = "CustomerPilotTimelineExported"
    # Sprint 67D — Customer pilot operations reliability
    CUSTOMER_PILOT_OPERATIONS_READINESS_EVALUATED = "CustomerPilotOperationsReadinessEvaluated"
    CUSTOMER_PILOT_NOTIFICATION_QUEUED = "CustomerPilotNotificationQueued"
    CUSTOMER_PILOT_NOTIFICATION_SENT = "CustomerPilotNotificationSent"
    CUSTOMER_PILOT_NOTIFICATION_FAILED = "CustomerPilotNotificationFailed"
    CUSTOMER_PILOT_NOTIFICATION_RETRIED = "CustomerPilotNotificationRetried"
    CUSTOMER_PILOT_NOTIFICATION_REQUEUED = "CustomerPilotNotificationRequeued"
    CUSTOMER_PILOT_SUPPORT_BUNDLE_GENERATED = "CustomerPilotSupportBundleGenerated"
    CUSTOMER_PILOT_SCHEDULER_DEGRADED = "CustomerPilotSchedulerDegraded"
    # Sprint 67E — Deployment readiness & internal dry run
    CUSTOMER_PILOT_DEPLOYMENT_READINESS_EVALUATED = "CustomerPilotDeploymentReadinessEvaluated"
    CUSTOMER_PILOT_DRY_RUN_COMPLETED = "CustomerPilotDryRunCompleted"


# Module-level subscriber registry (process-local). Handlers are idempotent and
# registered once at import time (see app.platform.activity).
_SUBSCRIBERS: dict[str, list[EventHandler]] = {}


def subscribe(event_type: str, handler: EventHandler) -> None:
    key = str(getattr(event_type, "value", event_type))
    handlers = _SUBSCRIBERS.setdefault(key, [])
    if handler not in handlers:
        handlers.append(handler)


def on(event_type: str) -> Callable[[EventHandler], EventHandler]:
    def decorator(handler: EventHandler) -> EventHandler:
        subscribe(event_type, handler)
        return handler

    return decorator


def clear_subscribers() -> None:  # test helper
    _SUBSCRIBERS.clear()


def register_default_subscribers() -> None:
    """Re-wire production subscribers cleared by ``clear_subscribers()`` in tests."""
    from app.core.config import settings
    from app.platform.activity import activity_event_handler

    subscribe("*", activity_event_handler)
    if settings.PRODUCT_EXCELLENCE_ENABLED:
        from app.platform.product import inbox_event_handler

        subscribe("*", inbox_event_handler)
    if settings.AUTONOMOUS_SRE_ENABLED:
        from app.platform.sre import sre_event_handler

        subscribe("*", sre_event_handler)
    if settings.AI_OPERATOR_ENABLED:
        from app.platform.operator_events import operator_event_handler

        subscribe("*", operator_event_handler)


def _handlers_for(event_type: str) -> list[EventHandler]:
    return [*_SUBSCRIBERS.get(event_type, []), *_SUBSCRIBERS.get("*", [])]


async def _redis_publish(event: DomainEvent) -> bool:
    """Best-effort cross-instance fan-out. Returns False when Redis is absent."""
    try:
        from app.redis.client import get_redis, key

        client = await get_redis()
        if client is None:
            return False
        channel = key("events", event.event_type)
        await client.publish(channel, json.dumps({
            "id": event.id,
            "event_type": event.event_type,
            "organization_id": event.organization_id,
            "aggregate_type": event.aggregate_type,
            "aggregate_id": event.aggregate_id,
            "payload": event.payload,
            "actor_id": event.actor_id,
            "source": event.source,
        }))
        return True
    except Exception as exc:  # pragma: no cover - redis optional
        logger.warning("event_redis_publish_failed", error=str(exc))
        return False


async def emit_event(
    session: AsyncSession,
    event_type: str | DomainEventType,
    *,
    organization_id: str | None = None,
    payload: dict | None = None,
    aggregate_type: str | None = None,
    aggregate_id: str | None = None,
    actor_id: str | None = None,
    source: str = "platform",
    idempotency_key: str | None = None,
) -> DomainEvent | None:
    """Best-effort emission used by domain services.

    Never raises: a failure to record/dispatch an event must not break the
    business operation that triggered it. Honours the convergence feature flag.
    """
    from app.core.config import settings

    if not getattr(settings, "PLATFORM_CONVERGENCE_ENABLED", True):
        return None
    try:
        return await EventBus(session).publish(
            event_type, organization_id=organization_id, payload=payload,
            aggregate_type=aggregate_type, aggregate_id=aggregate_id,
            actor_id=actor_id, source=source, idempotency_key=idempotency_key)
    except Exception as exc:  # noqa: BLE001 - emission is best-effort
        logger.warning("emit_event_failed", error=str(exc),
                       event_type=str(getattr(event_type, "value", event_type)))
        return None


class EventBus:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def publish(
        self,
        event_type: str | DomainEventType,
        *,
        organization_id: str | None = None,
        payload: dict | None = None,
        aggregate_type: str | None = None,
        aggregate_id: str | None = None,
        actor_id: str | None = None,
        source: str = "platform",
        max_attempts: int = 5,
        dispatch: bool = True,
        idempotency_key: str | None = None,
    ) -> DomainEvent:
        # Exactly-once / idempotent replication: a repeat publish with the same
        # key returns the existing event instead of creating a duplicate.
        if idempotency_key:
            existing = await self.session.scalar(
                select(DomainEvent).where(
                    DomainEvent.idempotency_key == idempotency_key))
            if existing is not None:
                return existing

        event = DomainEvent(
            event_type=str(getattr(event_type, "value", event_type)),
            organization_id=organization_id,
            payload=payload or {},
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            actor_id=actor_id,
            source=source,
            max_attempts=max_attempts,
            status=EventStatus.PENDING.value,
            idempotency_key=idempotency_key,
        )
        self.session.add(event)
        await self.session.flush()

        published = await _redis_publish(event)
        event.published_at = utcnow()
        _metric_event(event.event_type, "published" if published else "stored")
        if dispatch:
            await self._dispatch(event)
        else:
            await self.session.flush()
        return event

    async def _dispatch(self, event: DomainEvent) -> DomainEvent:
        handlers = _handlers_for(event.event_type)
        event.attempts = (event.attempts or 0) + 1
        errors: list[str] = []
        for handler in handlers:
            try:
                await handler(self.session, event)
            except Exception as exc:  # noqa: BLE001 - isolate handler failures
                errors.append(f"{getattr(handler, '__name__', 'handler')}: {exc}")
                logger.error("event_handler_failed", event_type=event.event_type,
                             handler=getattr(handler, "__name__", "?"), error=str(exc))
        if errors:
            event.error = "; ".join(errors)[:2000]
            # Poison-message handling: once attempts are exhausted the event is
            # dead-lettered (no further automatic delivery) so one bad event can
            # never block the consumer.
            event.status = (
                EventStatus.DEAD_LETTER.value
                if event.attempts >= event.max_attempts
                else EventStatus.FAILED.value
            )
        else:
            event.error = None
            event.status = EventStatus.PROCESSED.value
        event.consumed_at = utcnow()
        await self.session.flush()
        _metric_event(event.event_type, event.status)
        return event

    # ------------------------------------------------- durable consumer (acks)
    async def pending_count(self, *, organization_id: str | None = None) -> int:
        """Number of events still awaiting delivery (pending or retriable failed)."""
        stmt = select(func.count(DomainEvent.id)).where(
            DomainEvent.status.in_(
                (EventStatus.PENDING.value, EventStatus.FAILED.value)),
            DomainEvent.attempts < DomainEvent.max_attempts,
        )
        if organization_id is not None:
            stmt = stmt.where(DomainEvent.organization_id == organization_id)
        return int((await self.session.execute(stmt)).scalar() or 0)

    async def drain_pending(self, *, limit: int = 100) -> dict:
        """Deliver undelivered events from the durable outbox (consumer ack path).

        Selects PENDING (never dispatched) and retriable FAILED events oldest
        first, dispatches each (which acks via the PROCESSED/FAILED/DEAD_LETTER
        status transition). Idempotent + safe to run repeatedly; intended to be
        driven by a single leader-elected consumer so delivery is exactly-once.
        """
        stmt = (
            select(DomainEvent)
            .where(
                DomainEvent.status.in_(
                    (EventStatus.PENDING.value, EventStatus.FAILED.value)),
                DomainEvent.attempts < DomainEvent.max_attempts,
            )
            .order_by(DomainEvent.created_at)
            .limit(limit)
        )
        rows = list((await self.session.execute(stmt)).scalars().all())
        delivered = failed = 0
        for event in rows:
            result = await self._dispatch(event)
            if result.status == EventStatus.PROCESSED.value:
                delivered += 1
            else:
                failed += 1
        return {"claimed": len(rows), "delivered": delivered, "failed": failed}

    # ------------------------------------------------------------- replay/DLQ
    async def replay(self, event_id: str) -> DomainEvent | None:
        event = await self.session.get(DomainEvent, event_id)
        if event is None:
            return None
        _metric_replay("single")
        return await self._dispatch(event)

    async def retry_failed(self, *, organization_id: str | None = None,
                           limit: int = 100) -> int:
        stmt = select(DomainEvent).where(
            DomainEvent.status == EventStatus.FAILED.value)
        if organization_id is not None:
            stmt = stmt.where(DomainEvent.organization_id == organization_id)
        stmt = stmt.order_by(DomainEvent.created_at).limit(limit)
        rows = list((await self.session.execute(stmt)).scalars().all())
        for event in rows:
            await self._dispatch(event)
        if rows:
            _metric_replay("failed")
        return len(rows)

    async def replay_range(
        self,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        organization_id: str | None = None,
        event_type: str | None = None,
        statuses: tuple[str, ...] | None = None,
        limit: int = 1000,
    ) -> int:
        """Replay persisted events filtered by time range, org and/or type.

        Re-dispatches matching events (default: any status) so handlers run again
        — used for backfills, new-subscriber bootstrap and disaster recovery.
        """
        stmt = select(DomainEvent)
        if since is not None:
            stmt = stmt.where(DomainEvent.created_at >= since)
        if until is not None:
            stmt = stmt.where(DomainEvent.created_at <= until)
        if organization_id is not None:
            stmt = stmt.where(DomainEvent.organization_id == organization_id)
        if event_type is not None:
            stmt = stmt.where(DomainEvent.event_type == event_type)
        if statuses:
            stmt = stmt.where(DomainEvent.status.in_(statuses))
        stmt = stmt.order_by(DomainEvent.created_at).limit(limit)
        rows = list((await self.session.execute(stmt)).scalars().all())
        for event in rows:
            await self._dispatch(event)
        if rows:
            _metric_replay("range")
        return len(rows)

    async def requeue_dead_letter(self, event_id: str) -> DomainEvent | None:
        event = await self.session.get(DomainEvent, event_id)
        if event is None or event.status != EventStatus.DEAD_LETTER.value:
            return event
        event.attempts = 0
        event.status = EventStatus.PENDING.value
        await self.session.flush()
        return await self._dispatch(event)

    async def list_events(
        self,
        *,
        organization_id: str | None = None,
        event_type: str | None = None,
        status: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DomainEvent]:
        stmt = select(DomainEvent)
        if organization_id is not None:
            stmt = stmt.where(DomainEvent.organization_id == organization_id)
        if event_type is not None:
            stmt = stmt.where(DomainEvent.event_type == event_type)
        if status is not None:
            stmt = stmt.where(DomainEvent.status == status)
        if since is not None:
            stmt = stmt.where(DomainEvent.created_at >= since)
        stmt = stmt.order_by(DomainEvent.created_at.desc()).limit(limit).offset(offset)
        return list((await self.session.execute(stmt)).scalars().all())


# --------------------------------------------------------------------------- #
# Durable, leader-elected consumer
# --------------------------------------------------------------------------- #
async def drain_once(*, limit: int = 100) -> dict:
    """Open a session, drain a batch of pending events, publish the lag gauge."""
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        bus = EventBus(session)
        result = await bus.drain_pending(limit=limit)
        await session.commit()
        try:
            from app.observability import metrics

            metrics.set_event_pending(await bus.pending_count())
        except Exception:  # pragma: no cover
            pass
        return result


async def run_event_consumer(stop: asyncio.Event) -> None:
    """Leader-elected background loop that drains the durable event outbox.

    Only the elected leader across all replicas drains, so every event is
    delivered exactly once even under horizontal scaling. Falls back to a
    single-process drain when distributed locking is unavailable.
    """
    from app.core.config import settings
    from app.redis.locks import LeaderElector

    poll = max(0.2, float(settings.EVENT_CONSUMER_POLL_SECONDS))
    batch = max(1, int(settings.EVENT_CONSUMER_BATCH))
    elector = LeaderElector(
        "event_consumer", ttl_seconds=settings.EVENT_CONSUMER_LOCK_TTL_SECONDS)
    await elector.start()
    logger.info("event_consumer_started", poll_seconds=poll, batch=batch)
    try:
        while not stop.is_set():
            try:
                if elector.is_leader or await elector.try_acquire():
                    await drain_once(limit=batch)
            except Exception as exc:  # noqa: BLE001 - never let the loop die
                logger.warning("event_consumer_iteration_failed", error=str(exc))
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll)
            except TimeoutError:
                pass
    finally:
        await elector.stop()
        logger.info("event_consumer_stopped")
