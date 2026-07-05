"""Sprint 42A — Continuous Monitoring & Auto Incident Creation.

Transforms the platform from a reactive copilot into a proactive monitoring
platform:

    poll providers → detect alerts → deduplicate → auto-create incident
        → auto-investigate (reuse 40A) → timeline (40B) + change intel (40C)
        → recommendations (41A) → notify humans

It strictly REUSES the existing engines — it adds no new investigation,
timeline, change, or recommendation logic. It is read-only: it never deploys,
remediates, mutates infrastructure, or executes shell commands. Human approval
remains mandatory for any remediation (Sprint 41B/C), which this engine does not
trigger.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.config import settings
from app.core.exceptions import ForbiddenError
from app.models.incident import (
    IncidentEventSeverity,
    IncidentInvestigationStatus,
    IncidentSource,
    MonitoringAlert,
    MonitoringAlertStatus,
    MonitoringSeverity,
)
from app.models.monitoring_ingestion import DeadLetterSource
from app.models.user import User
from app.repositories.ai_team import AITeamAgentRepository
from app.repositories.audit import AuditLogRepository
from app.repositories.credential import DeploymentCredentialRepository
from app.repositories.incident import (
    IncidentInvestigationRepository,
    IncidentRecommendationRepository,
    IncidentRemediationActionRepository,
    IncidentTimelineEventRepository,
    MonitoringAlertRepository,
)
from app.repositories.monitoring_ingestion import MonitoringDeadLetterRepository
from app.repositories.oncall import OnCallScheduleRepository
from app.schemas.incident import IncidentInvestigateRequest
from app.schemas.monitoring import (
    CurrentOnCallEntry,
    MonitoringDashboardResponse,
    NormalizedAlertInput,
    RecentRemediation,
    ServiceCount,
    TrendPoint,
)
from app.security.secrets import SecretManagerService
from app.services.incident_investigation import IncidentInvestigationService
from app.services.incident_notifications import IncidentNotificationService
from app.services.monitoring_ingestion import (
    INGEST_POLLERS,
    INGEST_PROVIDERS,
    IngestError,
    NormalizedAlert,
    parse_webhook,
    poll_provider,
)
from app.services.oncall import (
    IncidentRoutingService,
    OnCallMetricsService,
    resolve_current_oncall,
)
from app.tenancy.permissions import can_read_ai_teams, can_write_ai_teams

logger = structlog.get_logger(__name__)

# Providers with live ingestion pollers (see monitoring_ingestion.INGEST_POLLERS).
MONITORING_PROVIDERS = set(INGEST_PROVIDERS)
# Severities that warrant an auto-created incident investigation.
AUTO_INCIDENT_SEVERITIES = {MonitoringSeverity.HIGH.value, MonitoringSeverity.CRITICAL.value}


def _investigation_context_from_alert(alert) -> dict:
    """Build provider-aware context for auto-investigation (Jenkins job/build, etc.)."""
    ctx: dict = {
        "provider": alert.provider,
        "service": alert.service,
        "environment": alert.environment,
        "alert_name": alert.alert_name,
    }
    labels = alert.labels or {}
    annotations = alert.annotations or {}
    provider = (alert.provider or "").upper()

    if provider == "JENKINS":
        job = labels.get("job") or alert.service
        if job:
            ctx["job"] = job
            ctx["pipeline"] = job
        if annotations.get("url"):
            ctx["build_url"] = annotations["url"]
        aid = alert.alert_id or ""
        if "#" in aid:
            ctx["build_number"] = aid.split("#", 1)[1]
        if labels.get("result"):
            ctx["build_result"] = labels["result"]
    elif provider == "GITHUB":
        if labels.get("workflow"):
            ctx["workflow"] = labels["workflow"]
        if annotations.get("url"):
            ctx["run_url"] = annotations["url"]
    elif provider == "GITLAB":
        if labels.get("ref"):
            ctx["ref"] = labels["ref"]
        if annotations.get("url"):
            ctx["pipeline_url"] = annotations["url"]

    return {k: v for k, v in ctx.items() if v}


def _auto_incident_prompt(alert, context: dict) -> str:
    """Human-readable investigation prompt with provider-specific detail."""
    scope = []
    if alert.service:
        scope.append(alert.service)
    if alert.environment:
        scope.append(alert.environment)
    scope_str = " / ".join(scope) if scope else "production"

    provider = (alert.provider or "").upper()
    if provider == "JENKINS" and context.get("job"):
        build = f" #{context['build_number']}" if context.get("build_number") else ""
        return (
            f"Jenkins build failed for job '{context['job']}'{build} on {scope_str}. "
            f"{alert.description or ''} "
            "Investigate pipeline logs, recent commits, and recommend concrete fixes."
        ).strip()

    return (
        f"A {alert.severity} alert '{alert.alert_name}' is firing on "
        f"{alert.provider} for {scope_str}. "
        f"{alert.description or ''} "
        "Investigate the root cause, correlate recent changes, and recommend remediation."
    ).strip()

_SEVERITY_ALIASES = {
    "INFO": MonitoringSeverity.INFO.value,
    "INFORMATIONAL": MonitoringSeverity.INFO.value,
    "LOW": MonitoringSeverity.INFO.value,
    "OK": MonitoringSeverity.INFO.value,
    "WARNING": MonitoringSeverity.WARNING.value,
    "WARN": MonitoringSeverity.WARNING.value,
    "MEDIUM": MonitoringSeverity.WARNING.value,
    "HIGH": MonitoringSeverity.HIGH.value,
    "ERROR": MonitoringSeverity.HIGH.value,
    "MAJOR": MonitoringSeverity.HIGH.value,
    "ALARM": MonitoringSeverity.HIGH.value,
    "CRITICAL": MonitoringSeverity.CRITICAL.value,
    "CRIT": MonitoringSeverity.CRITICAL.value,
    "FATAL": MonitoringSeverity.CRITICAL.value,
    "SEV1": MonitoringSeverity.CRITICAL.value,
    "P1": MonitoringSeverity.CRITICAL.value,
}

# Map monitoring severity → timeline event severity (INFO/WARNING/CRITICAL).
_EVENT_SEVERITY = {
    MonitoringSeverity.INFO.value: IncidentEventSeverity.INFO.value,
    MonitoringSeverity.WARNING.value: IncidentEventSeverity.WARNING.value,
    MonitoringSeverity.HIGH.value: IncidentEventSeverity.WARNING.value,
    MonitoringSeverity.CRITICAL.value: IncidentEventSeverity.CRITICAL.value,
}


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def normalize_severity(value: str | None) -> str:
    return _SEVERITY_ALIASES.get((value or "").strip().upper(), MonitoringSeverity.WARNING.value)


class MonitoringEngine:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.alert_repo = MonitoringAlertRepository(session)
        self.incident_repo = IncidentInvestigationRepository(session)
        self.event_repo = IncidentTimelineEventRepository(session)
        self.rec_repo = IncidentRecommendationRepository(session)
        self.action_repo = IncidentRemediationActionRepository(session)
        self.agent_repo = AITeamAgentRepository(session)
        self.cred_repo = DeploymentCredentialRepository(session)
        self.dlq_repo = MonitoringDeadLetterRepository(session)
        self.secret_manager = SecretManagerService(session)
        self.audit_repo = AuditLogRepository(session)
        self.investigation_service = IncidentInvestigationService(session)
        self.notifier = IncidentNotificationService(session)
        self.routing_service = IncidentRoutingService(session)
        self.oncall_metrics = OnCallMetricsService(session)
        self.schedule_repo = OnCallScheduleRepository(session)

    # ------------------------------------------------------------------ guards
    def _ensure_read(self, user: User, org_context: OrgContext) -> None:
        if not user.is_superuser and (
            not org_context.role or not can_read_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    def _ensure_write(self, user: User, org_context: OrgContext) -> None:
        if not user.is_superuser and (
            not org_context.role or not can_write_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    # --------------------------------------------------------------- ingestion
    @staticmethod
    def _correlation(provider: str, alert_name: str, service, environment, resource) -> str:
        basis = "|".join([provider, alert_name, service or "", environment or "", resource or ""])
        return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:24]  # noqa: S324

    def _normalize(self, raw: NormalizedAlertInput) -> dict:
        provider = raw.provider.strip().upper()
        alert_name = raw.alert_name.strip()
        service = raw.service or None
        environment = raw.environment or None
        resource = getattr(raw, "resource", None) or None
        return {
            "provider": provider,
            "alert_id": raw.alert_id.strip(),
            "alert_name": alert_name,
            "severity": normalize_severity(raw.severity),
            "status": (raw.status or "FIRING").strip().upper(),
            "service": service,
            "environment": environment,
            "description": (raw.description or None),
            "timestamp": _aware(raw.timestamp) or _now(),
            "resource": resource,
            "region": getattr(raw, "region", None) or None,
            "labels": getattr(raw, "labels", None) or {},
            "annotations": getattr(raw, "annotations", None) or {},
            "correlation_id": (getattr(raw, "correlation_id", None)
                               or self._correlation(provider, alert_name, service, environment, resource)),
        }

    def _normalize_na(self, na: NormalizedAlert) -> dict:
        """Convert a live-poller / webhook ``NormalizedAlert`` to the canonical dict."""
        na = na.with_correlation()
        provider = (na.provider or "").strip().upper()
        return {
            "provider": provider,
            "alert_id": (na.alert_id or na.alert_name or "alert").strip()[:200],
            "alert_name": (na.alert_name or "alert").strip()[:255],
            "severity": normalize_severity(na.severity),
            "status": (na.status or "FIRING").strip().upper(),
            "service": na.service or None,
            "environment": na.environment or None,
            "description": na.description or None,
            "timestamp": _aware(na.timestamp) or _now(),
            "resource": na.resource or None,
            "region": na.region or None,
            "labels": na.labels or {},
            "annotations": na.annotations or {},
            "correlation_id": na.correlation_id,
        }

    async def _record_dead_letter(
        self, organization_id: str, provider: str, source: str, error: str,
        *, attempts: int = 3, payload: object | None = None, context: dict | None = None,
    ) -> None:
        digest = None
        if payload is not None:
            try:
                digest = hashlib.sha1(  # noqa: S324
                    json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
                ).hexdigest()
            except (TypeError, ValueError):
                digest = None
        await self.dlq_repo.create(
            organization_id=organization_id, provider=provider, source=source,
            error=error[:2000], attempts=attempts, payload_digest=digest, context=context or {},
        )

    async def collect_alerts(
        self, user: User, org_context: OrgContext, providers: list[str] | None
    ) -> list[dict]:
        """Real read-only ingestion from connected monitoring providers.

        Polls both deployment credentials and marketplace integration connections
        (deduplicated by credential id). Per-provider failures are dead-lettered
        and never abort the cycle.
        """
        organization_id = org_context.requires_organization
        wanted = {p.upper() for p in (providers or MONITORING_PROVIDERS)} & MONITORING_PROVIDERS

        from app.services.integration_poll_sources import list_ingest_targets

        targets = await list_ingest_targets(self.session, organization_id, wanted)

        started = time.monotonic()
        received: list[dict] = []
        failures = 0
        polled_providers: set[str] = set()

        for target in targets:
            provider = target.provider
            try:
                _, secret = await self.secret_manager.resolve_secret(
                    target.credential_id, user=user, org_context=org_context,
                    reason="monitoring ingestion", audit=False,
                )
            except Exception as exc:  # noqa: BLE001 - customer-safe
                failures += 1
                logger.info("monitoring_credential_unavailable", provider=provider,
                            error=type(exc).__name__, source=target.source)
                await self._record_dead_letter(
                    organization_id, provider, DeadLetterSource.POLL.value,
                    "Credential unavailable for ingestion.",
                    context={"reason": type(exc).__name__, "source": target.source})
                continue
            try:
                alerts = await poll_provider(provider, secret)
            except IngestError as exc:
                failures += 1
                await self._record_dead_letter(
                    organization_id, provider, DeadLetterSource.POLL.value, str(exc))
                continue
            except Exception as exc:  # noqa: BLE001 - never surface internals
                failures += 1
                logger.warning("monitoring_poll_failed", provider=provider, error=type(exc).__name__)
                await self._record_dead_letter(
                    organization_id, provider, DeadLetterSource.POLL.value,
                    f"Unexpected ingestion failure: {type(exc).__name__}")
                continue
            polled_providers.add(provider)
            for na in alerts:
                received.append(self._normalize_na(na))

        self._ingest_metrics = {
            "alerts_received": len(received),
            "failures": failures,
            "providers_polled": sorted(polled_providers),
            "latency_ms": int((time.monotonic() - started) * 1000),
        }
        logger.info("monitoring_collect_alerts", organization_id=organization_id,
                    polled=sorted(polled_providers), received=len(received), failures=failures)
        return received

    # ----------------------------------------------------------------- polling
    async def poll(
        self,
        user: User,
        org_context: OrgContext,
        *,
        provided_alerts: list[NormalizedAlertInput] | None = None,
        providers: list[str] | None = None,
    ) -> dict:
        """Run one monitoring cycle for a single organization.

        poll → detect → deduplicate → create incidents → investigate → notify.
        """
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)

        self._ingest_metrics = {"alerts_received": 0, "failures": 0,
                                "providers_polled": [], "latency_ms": 0}
        started = time.monotonic()

        if provided_alerts is not None:
            normalized = [self._normalize(a) for a in provided_alerts]
            polled_providers = sorted({n["provider"] for n in normalized})
        else:
            normalized = await self.collect_alerts(user, org_context, providers)
            polled = self._ingest_metrics.get("providers_polled") or []
            polled_providers = sorted(
                set(polled)
                or (({p.upper() for p in providers} & MONITORING_PROVIDERS)
                    if providers else set())
            )

        summary = await self._process_batch(user, org_context, organization_id, normalized)
        summary["polled_providers"] = polled_providers
        summary["metrics"] = self._build_metrics(summary, started)

        await self.audit_repo.log(
            action="monitoring_poll_completed",
            resource_type="monitoring",
            resource_id=organization_id,
            user_id=user.id,
            details={
                "polled_providers": polled_providers,
                "alerts_received": summary["metrics"]["alerts_received"],
                "alerts_processed": summary["metrics"]["alerts_processed"],
                "new_alerts": summary["new_alerts"],
                "deduplicated": summary["deduplicated"],
                "incidents_created": summary["incidents_created"],
                "failures": summary["metrics"]["failures"],
                "latency_ms": summary["metrics"]["latency_ms"],
            },
        )
        await self.session.commit()
        return summary

    def _build_metrics(self, summary: dict, started: float) -> dict:
        ingest = getattr(self, "_ingest_metrics", {}) or {}
        return {
            # received = what providers emitted (collect) or what was pushed in
            "alerts_received": ingest.get("alerts_received") or summary["alerts_ingested"],
            "alerts_processed": summary["alerts_ingested"],
            "failures": ingest.get("failures", 0),
            "latency_ms": int((time.monotonic() - started) * 1000),
        }

    async def _process_batch(
        self, user: User, org_context: OrgContext, organization_id: str, normalized: list[dict]
    ) -> dict:
        summary = {
            "polled_providers": [],
            "alerts_ingested": 0,
            "new_alerts": 0,
            "deduplicated": 0,
            "incidents_created": 0,
            "notifications_sent": 0,
            "alerts": [],
        }
        for alert in normalized:
            if alert["provider"] not in MONITORING_PROVIDERS:
                continue
            result = await self._process_alert(user, org_context, organization_id, alert)
            summary["alerts_ingested"] += 1
            summary["alerts"].append(result["alert"])
            if result["deduplicated"]:
                summary["deduplicated"] += 1
            else:
                summary["new_alerts"] += 1
            if result["incident_created"]:
                summary["incidents_created"] += 1
            summary["notifications_sent"] += result["notifications_sent"]
        return summary

    async def ingest_webhook(
        self, user: User, org_context: OrgContext, provider: str, payload: dict
    ) -> dict:
        """Sprint 58A.3 — push ingestion from a provider webhook (org-scoped).

        Parses the provider payload into normalized alerts and runs the same
        dedup → correlate → auto-incident → notify pipeline as polling. Malformed
        payloads are dead-lettered (never dropped silently)."""
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        provider = (provider or "").strip().upper()
        started = time.monotonic()
        self._ingest_metrics = {"alerts_received": 0, "failures": 0,
                                "providers_polled": [provider], "latency_ms": 0}

        try:
            parsed = parse_webhook(provider, payload)
        except IngestError as exc:
            await self._record_dead_letter(
                organization_id, provider, DeadLetterSource.WEBHOOK.value, str(exc),
                attempts=1, payload=payload)
            await self.audit_repo.log(
                action="monitoring_webhook_dead_lettered", resource_type="monitoring",
                resource_id=organization_id, user_id=user.id,
                details={"provider": provider, "error": str(exc)})
            await self.session.commit()
            raise

        normalized = [self._normalize_na(na) for na in parsed]
        self._ingest_metrics["alerts_received"] = len(normalized)
        summary = await self._process_batch(user, org_context, organization_id, normalized)
        summary["polled_providers"] = [provider]
        summary["metrics"] = self._build_metrics(summary, started)

        await self.audit_repo.log(
            action="monitoring_webhook_ingested", resource_type="monitoring",
            resource_id=organization_id, user_id=user.id,
            details={"provider": provider,
                     "alerts_received": summary["metrics"]["alerts_received"],
                     "alerts_processed": summary["metrics"]["alerts_processed"],
                     "incidents_created": summary["incidents_created"]},
        )
        await self.session.commit()
        return summary

    async def list_dead_letters(
        self, user: User, org_context: OrgContext, *, status: str | None = None, limit: int = 100
    ):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        return await self.dlq_repo.list_for_org(organization_id, status=status, limit=limit)

    @staticmethod
    def _dedup_key(organization_id: str, alert: dict) -> str:
        """Stable identity for an alert used by the atomic-dedup unique index."""
        raw = "|".join(
            [
                organization_id,
                alert.get("provider") or "",
                alert.get("alert_name") or "",
                alert.get("service") or "",
                alert.get("environment") or "",
            ]
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    async def _collapse_onto(
        self, existing: MonitoringAlert, user: User, organization_id: str, alert: dict
    ) -> dict:
        # Alert storm protection: collapse onto the existing incident.
        existing.occurrence_count += 1
        existing.last_seen_at = alert["timestamp"]
        if alert["status"] == MonitoringAlertStatus.RESOLVED.value:
            existing.status = MonitoringAlertStatus.RESOLVED.value
        await self.session.flush()
        await self.audit_repo.log(
            action="monitoring_alert_deduplicated",
            resource_type="monitoring_alert",
            resource_id=existing.id,
            user_id=user.id,
            details={
                "organization_id": organization_id,
                "provider": existing.provider,
                "alert_name": existing.alert_name,
                "occurrence_count": existing.occurrence_count,
            },
        )
        return {
            "alert": existing,
            "deduplicated": True,
            "incident_created": False,
            "notifications_sent": 0,
        }

    async def _process_alert(
        self, user: User, org_context: OrgContext, organization_id: str, alert: dict
    ) -> dict:
        window = timedelta(minutes=max(1, settings.MONITORING_DEDUP_WINDOW_MINUTES))
        since = _now() - window
        dedup_key = self._dedup_key(organization_id, alert)
        existing = await self.alert_repo.find_recent_duplicate(
            organization_id=organization_id,
            provider=alert["provider"],
            alert_name=alert["alert_name"],
            service=alert["service"],
            environment=alert["environment"],
            since=since,
        )
        if existing is not None:
            return await self._collapse_onto(existing, user, organization_id, alert)

        create_kwargs = dict(
            organization_id=organization_id,
            provider=alert["provider"],
            alert_id=alert["alert_id"],
            alert_name=alert["alert_name"],
            severity=alert["severity"],
            status=alert["status"],
            service=alert["service"],
            environment=alert["environment"],
            description=alert["description"],
            first_seen_at=alert["timestamp"],
            last_seen_at=alert["timestamp"],
            occurrence_count=1,
            resource=alert.get("resource"),
            region=alert.get("region"),
            labels=alert.get("labels") or {},
            annotations=alert.get("annotations") or {},
            correlation_id=alert.get("correlation_id"),
            dedup_key=dedup_key,
        )
        try:
            # Insert inside a savepoint so a concurrent winner's unique-index
            # violation can be recovered without poisoning the outer transaction.
            async with self.session.begin_nested():
                row = await self.alert_repo.create(**create_kwargs)
        except IntegrityError:
            # Lost the race: another ingest created the active alert first.
            # Collapse onto it instead of creating a duplicate.
            winner = await self.alert_repo.find_active_by_dedup_key(
                organization_id=organization_id, dedup_key=dedup_key
            )
            if winner is not None:
                return await self._collapse_onto(winner, user, organization_id, alert)
            # Extremely unlikely (winner resolved in between) — re-raise.
            raise
        await self.audit_repo.log(
            action="monitoring_alert_created",
            resource_type="monitoring_alert",
            resource_id=row.id,
            user_id=user.id,
            details={
                "organization_id": organization_id,
                "provider": row.provider,
                "alert_name": row.alert_name,
                "severity": row.severity,
            },
        )

        incident_created = False
        notifications_sent = 0
        if row.severity in AUTO_INCIDENT_SEVERITIES and alert["status"] != MonitoringAlertStatus.RESOLVED.value:
            incident_id, notifications_sent = await self._auto_create_incident(
                user, org_context, organization_id, row, alert_dict=alert,
            )
            if incident_id:
                row.incident_id = incident_id
                await self.session.flush()
                incident_created = True

        return {
            "alert": row,
            "deduplicated": False,
            "incident_created": incident_created,
            "notifications_sent": notifications_sent,
        }

    # ------------------------------------------------------ auto incident path
    async def _resolve_team_id(self, organization_id: str) -> str | None:
        agents, _ = await self.agent_repo.list_by_organization(
            organization_id, is_active=True, limit=1
        )
        return agents[0].team_id if agents else None

    async def _auto_create_incident(
        self,
        user: User,
        org_context: OrgContext,
        organization_id: str,
        alert,
        *,
        alert_dict: dict | None = None,
    ) -> tuple[str | None, int]:
        title = f"[{alert.severity}] {alert.alert_name}"[:255]
        context = _investigation_context_from_alert(alert)
        if alert_dict:
            for key in ("resource", "region", "description"):
                if alert_dict.get(key) and key not in context:
                    context[key] = alert_dict[key]
        prompt = _auto_incident_prompt(alert, context)

        team_id = await self._resolve_team_id(organization_id)
        incident_id: str | None = None

        if team_id:
            # Reuse the Sprint 40A investigation engine verbatim (timeline 40B,
            # change intelligence 40C, recommendations 41A all run inside).
            try:
                detail = await self.investigation_service.investigate(
                    IncidentInvestigateRequest(
                        team_id=team_id,
                        title=title,
                        prompt=prompt,
                        context=context,
                    ),
                    user,
                    org_context,
                )
                incident_id = detail.id
            except Exception as exc:  # pragma: no cover - investigation guards itself
                logger.error("monitoring_auto_investigation_failed", error=str(exc))
                incident_id = None

        if incident_id is None:
            # Fallback: no AI team configured (or investigation failed). Still
            # auto-create the incident record so nothing is dropped.
            inv = await self.incident_repo.create(
                organization_id=organization_id,
                title=title,
                prompt=prompt,
                status=IncidentInvestigationStatus.RUNNING.value,
                suspected_provider=alert.provider,
                created_by=user.id,
            )
            await self.session.flush()
            incident_id = inv.id

        # Tag provenance + severity on the incident row.
        inv = await self.incident_repo.get_for_org(incident_id, organization_id)
        if inv is not None:
            inv.source = IncidentSource.MONITORING.value
            inv.severity = alert.severity
            await self.session.flush()

        await self._prepend_alert_event(organization_id, incident_id, alert)

        await self.audit_repo.log(
            action="monitoring_incident_created",
            resource_type="incident_investigation",
            resource_id=incident_id,
            user_id=user.id,
            details={
                "organization_id": organization_id,
                "alert_provider": alert.provider,
                "severity": alert.severity,
                "source": IncidentSource.MONITORING.value,
            },
        )

        # Sprint 42B — route the incident to its owner + current on-call engineer
        # and page the responder (the routing service handles notification).
        notifications_sent = 0
        try:
            _, notifications_sent = await self.routing_service.route_incident(
                user,
                org_context,
                incident_id,
                service_name=alert.service,
                severity=alert.severity,
                commit=False,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("monitoring_incident_routing_failed", error=str(exc))
        else:
            await self._send_rca_notification(
                user, organization_id, incident_id, alert.severity,
            )
        return incident_id, notifications_sent

    async def _prepend_alert_event(self, organization_id: str, incident_id: str, alert) -> None:
        """Ensure ALERT_DETECTED is the first event on the timeline."""
        existing = await self.event_repo.list_for_investigation(incident_id, organization_id)
        earliest = min((_aware(e.event_timestamp) for e in existing), default=None)
        ts = _aware(alert.first_seen_at) or _now()
        if earliest is not None and earliest <= ts:
            ts = earliest - timedelta(seconds=1)
        await self.event_repo.create(
            investigation_id=incident_id,
            organization_id=organization_id,
            provider=alert.provider,
            event_type="ALERT_DETECTED",
            event_timestamp=ts,
            title=f"Alert detected: {alert.alert_name}"[:255],
            description=(alert.description or f"{alert.severity} alert firing on {alert.provider}")[:1000],
            severity=_EVENT_SEVERITY.get(alert.severity, IncidentEventSeverity.WARNING.value),
            event_metadata={
                "alert_id": alert.alert_id,
                "service": alert.service,
                "environment": alert.environment,
                "occurrence_count": alert.occurrence_count,
            },
        )

    # ------------------------------------------------------------------- reads
    async def list_alerts(
        self,
        user: User,
        org_context: OrgContext,
        *,
        status: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        return await self.alert_repo.list_for_org(
            organization_id, status=status, offset=offset, limit=limit
        )

    async def get_alert(self, user: User, org_context: OrgContext, alert_id: str):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        return await self.alert_repo.get_for_org(alert_id, organization_id)

    async def investigate_alert(
        self, user: User, org_context: OrgContext, alert_id: str,
    ) -> dict:
        """Manually triage an alert into an incident + AI investigation (any severity)."""
        from app.core.exceptions import NotFoundError

        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        row = await self.alert_repo.get_for_org(alert_id, organization_id)
        if row is None:
            raise NotFoundError("Alert not found")

        if row.incident_id:
            return {
                "alert_id": row.id,
                "incident_id": row.incident_id,
                "created": False,
                "investigated": True,
                "message": "Alert already linked to an incident.",
            }

        if row.status == MonitoringAlertStatus.RESOLVED.value:
            return {
                "alert_id": row.id,
                "incident_id": None,
                "created": False,
                "investigated": False,
                "message": "Resolved alerts are not investigated.",
            }

        alert_dict = {
            "provider": row.provider,
            "alert_id": row.alert_id,
            "alert_name": row.alert_name,
            "severity": row.severity,
            "status": row.status,
            "service": row.service,
            "environment": row.environment,
            "description": row.description,
            "resource": row.resource,
            "region": row.region,
            "labels": row.labels or {},
            "annotations": row.annotations or {},
        }
        incident_id, _ = await self._auto_create_incident(
            user, org_context, organization_id, row, alert_dict=alert_dict,
        )
        if incident_id:
            row.incident_id = incident_id
            await self.session.flush()
            await self._send_rca_notification(
                user, organization_id, incident_id, alert_dict.get("severity"),
            )

        await self.session.commit()
        return {
            "alert_id": row.id,
            "incident_id": incident_id,
            "created": bool(incident_id),
            "investigated": bool(incident_id),
            "message": "Investigation complete." if incident_id else "Investigation failed.",
        }

    async def _send_rca_notification(
        self,
        user: User,
        organization_id: str,
        incident_id: str,
        severity: str | None,
    ) -> None:
        """Supplemental notification with RCA summary after investigation completes."""
        if not settings.NOTIFICATIONS_ENABLED:
            return
        inv = await self.incident_repo.get_for_org(incident_id, organization_id)
        if inv is None:
            return
        recs = await self.rec_repo.list_for_investigation(incident_id, organization_id)
        top = recs[0] if recs else None
        try:
            await self.notifier.notify_incident(
                organization_id=organization_id,
                incident_id=incident_id,
                title=inv.title,
                severity=severity or inv.severity or "HIGH",
                suspected_cause=inv.root_cause or inv.suspected_trigger,
                confidence=inv.confidence_score,
                recommended_action=(top.title if top else None),
                user_id=user.id,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("monitoring_rca_notification_failed", error=str(exc))

    async def dashboard(self, user: User, org_context: OrgContext) -> MonitoringDashboardResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)

        alerts, _ = await self.alert_repo.list_for_org(organization_id, limit=500)
        incidents, _ = await self.incident_repo.list_for_org(organization_id, limit=500)

        active_alerts = [a for a in alerts if a.status == MonitoringAlertStatus.FIRING.value]
        open_incidents = [
            i for i in incidents if i.status == IncidentInvestigationStatus.RUNNING.value
        ]
        critical_incidents = [
            i for i in incidents if (i.severity or "").upper() == MonitoringSeverity.CRITICAL.value
        ]

        await self.audit_repo.log(
            action="monitoring_dashboard_viewed",
            resource_type="monitoring",
            resource_id=organization_id,
            user_id=user.id,
            details={"active_alerts": len(active_alerts), "open_incidents": len(open_incidents)},
        )
        # Sprint 42B — on-call & escalation slice.
        oncall_summary = await self.oncall_metrics.dashboard_summary(organization_id)
        schedules = await self.schedule_repo.list_for_org(organization_id, active_only=True)
        current_oncall = [
            CurrentOnCallEntry(
                schedule_id=s.id,
                schedule_name=s.name,
                team=s.team,
                user_id=resolve_current_oncall(s),
            )
            for s in schedules
        ]

        await self.session.commit()

        return MonitoringDashboardResponse(
            active_alerts=len(active_alerts),
            open_incidents=len(open_incidents),
            critical_incidents=len(critical_incidents),
            mttr_minutes=self._mttr(incidents),
            total_incidents=len(incidents),
            incident_trend=self._trend(incidents),
            top_affected_services=self._top_services(alerts),
            recent_remediations=await self._recent_remediations(organization_id),
            recent_alerts=active_alerts[:10],
            unacknowledged_incidents=oncall_summary["unacknowledged_incidents"],
            escalated_incidents=oncall_summary["escalated_incidents"],
            mtta_minutes=oncall_summary["mtta_minutes"],
            current_oncall=current_oncall,
            dead_letters=await self.dlq_repo.count_pending(organization_id),
        )

    def _mttr(self, incidents: list) -> float | None:
        deltas = []
        for i in incidents:
            if i.status == IncidentInvestigationStatus.COMPLETED.value:
                start = _aware(i.created_at)
                end = _aware(getattr(i, "updated_at", None))
                if start and end and end >= start:
                    deltas.append((end - start).total_seconds() / 60.0)
        if not deltas:
            return None
        return round(sum(deltas) / len(deltas), 1)

    def _trend(self, incidents: list) -> list[TrendPoint]:
        now = _now()
        points: list[TrendPoint] = []
        for w in range(7, -1, -1):
            start = now - timedelta(days=7 * (w + 1))
            end = now - timedelta(days=7 * w)
            count = sum(1 for i in incidents if start <= (_aware(i.created_at) or now) < end)
            points.append(TrendPoint(period=end.strftime("%b %d"), count=count))
        return points

    def _top_services(self, alerts: list) -> list[ServiceCount]:
        counts: dict[str, int] = {}
        for a in alerts:
            key = a.service or "unknown"
            counts[key] = counts.get(key, 0) + a.occurrence_count
        ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
        return [ServiceCount(service=s, count=c) for s, c in ranked]

    async def _recent_remediations(self, organization_id: str) -> list[RecentRemediation]:
        actions = await self.action_repo.list_for_org(organization_id, limit=5)
        return [
            RecentRemediation(
                id=a.id,
                investigation_id=a.investigation_id,
                title=a.title,
                provider=a.provider,
                status=a.status,
                risk_level=a.risk_level,
                created_at=a.created_at,
            )
            for a in actions
        ]
