"""Integration readiness orchestration (Sprint 65G)."""

from __future__ import annotations

import hashlib
import time
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.config import settings
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.integration_readiness.capabilities import (
    build_capability_matrix,
    enforce_write_allowed,
)
from app.integration_readiness.evidence import build_live_evidence, redact_text
from app.integration_readiness.lifecycle import (
    health_score_from_result,
    map_verification_status,
    should_transition_state,
)
from app.integration_readiness.preflight import preflight_live_operation
from app.integration_readiness.probes import (
    probe_kubernetes,
    probe_marketplace_connection,
    probe_notification,
    probe_observability,
    probe_security_binary,
)
from app.models.integration_readiness import (
    IntConnectionRegistry,
    IntExpiryReminder,
    IntHealthHistory,
    IntLiveEvidence,
)
from app.models.observability_platform import ObsIntegration
from app.models.security_platform import SecProvider
from app.models.user import User
from app.platform.events import DomainEventType, emit_event
from app.repositories.audit import AuditLogRepository
from app.repositories.integration import IntegrationConnectionRepository
from app.repositories.integration_readiness import (
    IntExpiryRepo,
    IntHealthHistoryRepo,
    IntLiveEvidenceRepo,
    IntRegistryRepo,
)
from app.schemas.integration_readiness import (
    CapabilitiesView,
    ConnectionReadinessView,
    ExpiryReminderView,
    HealthHistoryEntry,
    HealthView,
    IntegrationDashboard,
    ProviderSummary,
    ValidateResponse,
)
from app.services.integration_capabilities import supports_pipeline_sync
from app.services.integration_sync import IntegrationSyncService
from app.security.secrets import SecretManagerService
from app.services.integration_verification import VStatus
from app.tenancy.permissions import can_read_resources, can_write_resources

logger = structlog.get_logger(__name__)

FEATURE_IMPACT = {
    "KUBERNETES": ["Control Plane", "Kubernetes Operations", "Release Reliability", "Universal Discovery"],
    "GITHUB": ["Delivery Platform", "GitOps", "Failed Workflow Alerts", "Universal Discovery"],
    "GITLAB": ["Delivery Platform", "GitOps", "Pipeline Alerts", "Universal Discovery"],
    "PROMETHEUS": ["Observability Platform", "Release Reliability", "Alert Ingestion"],
    "LOKI": ["Observability Platform", "Release Reliability"],
    "ARGOCD": ["GitOps", "Release Reliability", "Application Discovery"],
    "SLACK": ["Notifications", "Collaboration Discovery"],
    "TRIVY": ["Security Platform"],
    "JENKINS": ["Delivery Pipelines", "Build Alerts", "CI Discovery", "DORA Metrics"],
    "CIRCLECI": ["Delivery Pipelines", "Pipeline Alerts", "CI Discovery"],
    "AZURE_DEVOPS": ["Delivery Pipelines", "Repo Discovery", "DORA Metrics"],
    "AWS": ["Cloud Discovery", "CloudWatch Alerts", "Control Plane"],
    "AZURE": ["Cloud Discovery", "Azure Monitor Alerts", "Control Plane"],
    "GCP": ["Cloud Discovery", "Control Plane"],
    "DATADOG": ["Observability Platform", "Monitor Alerts"],
    "PAGERDUTY": ["Incidents", "On-call Context", "Open Incident Ingest"],
    "OPSGENIE": ["Incidents", "On-call Context", "Alert Ingest"],
    "JIRA": ["Change Correlation", "Project Discovery"],
    "MICROSOFT_TEAMS": ["Notifications", "Collaboration Discovery"],
    "TERRAFORM": ["Platform Engineering", "Workspace Discovery", "IaC Runs"],
    "ALERTMANAGER": ["Observability Platform", "Alert Ingestion"],
    "CLOUDWATCH": ["Observability Platform", "Alert Ingestion"],
    "SONARQUBE": ["Security Platform", "Quality Gates"],
    "HASHICORP_VAULT": ["Secrets Management", "Vault Discovery"],
    "GRAFANA": ["Observability Platform"],
    "NEW_RELIC": ["Observability Platform", "APM Context"],
    "ELASTIC": ["Observability Platform", "Log Search"],
    "BITBUCKET": ["Delivery Platform", "Repo Discovery", "Pipeline Alerts"],
    "GCP": ["Cloud Discovery", "Control Plane", "GKE Inventory"],
    "GRAFANA": ["Observability Platform", "Dashboard Discovery", "Alert Ingest"],
    "NEW_RELIC": ["Observability Platform", "APM Context", "Incident Ingest"],
    "LOKI": ["Observability Platform", "Log Discovery", "Alert Ingest"],
    "ELASTIC": ["Observability Platform", "Index Discovery", "Cluster Alerts"],
    "CLOUDWATCH": ["Observability Platform", "Alert Ingestion"],
    "HASHICORP_VAULT": ["Secrets Management", "Vault Discovery"],
    "SONARQUBE": ["Security Platform", "Quality Gates", "Issue Alerts"],
    "MICROSOFT_TEAMS": ["Notifications", "Collaboration Discovery"],
    "SPLUNK": ["Observability Platform", "Log Search", "Notable Events"],
    "SERVICENOW": ["Incidents", "Change Correlation", "CMDB Discovery"],
    "OPENTELEMETRY": ["Observability Platform", "Metrics Explorer", "Trace Explorer"],
    "SENTRY": ["Observability Platform", "Error Ingest"],
    "DYNATRACE": ["Observability Platform", "APM Context"],
    "BUILDKITE": ["Delivery Platform", "Build Alerts"],
    "HARNESS": ["Delivery Platform", "Pipeline Alerts"],
    "FLUX": ["Delivery GitOps", "GitOps Discovery"],
}

EXPIRY_WINDOWS = ("30d", "14d", "7d", "1d")
EXPIRY_DAYS = {"30d": 30, "14d": 14, "7d": 7, "1d": 1}


def _idempotency_key(org_id: str, resource_type: str, resource_id: str) -> str:
    raw = f"{org_id}:{resource_type}:{resource_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


def _redact_failure(errors: list[str] | None) -> str | None:
    if not errors:
        return None
    return redact_text("; ".join(errors)[:500])


class IntegrationReadinessService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.registry = IntRegistryRepo(session)
        self.history = IntHealthHistoryRepo(session)
        self.expiry = IntExpiryRepo(session)
        self.evidence = IntLiveEvidenceRepo(session)
        self.connections = IntegrationConnectionRepository(session)
        self.secrets = SecretManagerService(session)
        self.audit = AuditLogRepository(session)

    def _ensure_read(self, user: User, org_context: OrgContext) -> str:
        if not can_read_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    def _ensure_write(self, user: User, org_context: OrgContext) -> str:
        if not can_write_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    async def _get_registry(self, organization_id: str, registry_id: str) -> IntConnectionRegistry:
        row = await self.registry.get_by_id(registry_id)
        if row and row.organization_id == organization_id:
            return row
        # Integrations UI routes use marketplace connection ids — resolve via resource_id.
        row = await self.registry.get_by_resource(organization_id, "marketplace", registry_id)
        if row:
            return row
        raise NotFoundError("IntegrationConnection", registry_id)

    async def sync_registry(self, organization_id: str) -> int:
        """Upsert registry rows from canonical connection tables."""
        synced = 0
        conns = await self.connections.list_for_org(organization_id)
        for conn in conns:
            key = _idempotency_key(organization_id, "marketplace", conn.id)
            existing = await self.registry.get_by_idempotency(organization_id, key)
            if existing:
                continue
            row = IntConnectionRegistry(
                organization_id=organization_id,
                resource_type="marketplace",
                resource_id=conn.id,
                provider_type=conn.integration_key.upper(),
                credential_id=conn.credential_id,
                lifecycle_state="DRAFT",
                provider_mode="unavailable",
                capabilities={},
                idempotency_key=key,
            )
            self.session.add(row)
            synced += 1

        obs_stmt = select(ObsIntegration).where(ObsIntegration.organization_id == organization_id)
        for obs in (await self.session.execute(obs_stmt)).scalars().all():
            key = _idempotency_key(organization_id, "observability", obs.id)
            if await self.registry.get_by_idempotency(organization_id, key):
                continue
            self.session.add(IntConnectionRegistry(
                organization_id=organization_id,
                resource_type="observability",
                resource_id=obs.id,
                provider_type=(obs.kind or "PROMETHEUS").upper(),
                credential_id=getattr(obs, "credential_id", None),
                lifecycle_state="DRAFT",
                provider_mode="offline",
                capabilities={},
                idempotency_key=key,
            ))
            synced += 1

        sec_stmt = select(SecProvider).where(SecProvider.organization_id == organization_id)
        for sec in (await self.session.execute(sec_stmt)).scalars().all():
            key = _idempotency_key(organization_id, "security", sec.id)
            if await self.registry.get_by_idempotency(organization_id, key):
                continue
            self.session.add(IntConnectionRegistry(
                organization_id=organization_id,
                resource_type="security",
                resource_id=sec.id,
                provider_type=(sec.provider_type or "TRIVY").upper(),
                credential_id=getattr(sec, "credential_id", None),
                lifecycle_state="DRAFT",
                provider_mode="offline",
                capabilities={},
                idempotency_key=key,
            ))
            synced += 1

        if synced:
            await self.session.flush()
        return synced

    async def list_providers(self, user: User, org_context: OrgContext) -> list[ProviderSummary]:
        organization_id = self._ensure_read(user, org_context)
        await self.sync_registry(organization_id)
        rows = await self.registry.list_for_org(organization_id)
        counts: dict[str, dict[str, int]] = {}
        for row in rows:
            bucket = counts.setdefault(row.provider_type, {"total": 0, "connected": 0, "degraded": 0, "failed": 0})
            bucket["total"] += 1
            if row.lifecycle_state == "CONNECTED":
                bucket["connected"] += 1
            elif row.lifecycle_state == "DEGRADED":
                bucket["degraded"] += 1
            elif row.lifecycle_state in ("FAILED", "EXPIRED", "REAUTH_REQUIRED"):
                bucket["failed"] += 1
        return [ProviderSummary(provider_type=k, **v) for k, v in sorted(counts.items())]

    async def list_connections(
        self, user: User, org_context: OrgContext, *, state: str | None = None,
    ) -> list[ConnectionReadinessView]:
        organization_id = self._ensure_read(user, org_context)
        await self.sync_registry(organization_id)
        rows = await self.registry.list_for_org(organization_id, state=state)
        return [self._to_connection_view(r) for r in rows]

    def _to_connection_view(self, row: IntConnectionRegistry) -> ConnectionReadinessView:
        impact = FEATURE_IMPACT.get(row.provider_type, ["Platform Integrations"])
        remediation = None
        if row.lifecycle_state == "REAUTH_REQUIRED":
            remediation = "Renew credentials and re-validate the connection."
        elif row.lifecycle_state == "FAILED":
            remediation = row.failure_reason or "Run validation to diagnose connectivity issues."
        elif row.lifecycle_state == "DEGRADED":
            remediation = "Some capabilities are missing; review permissions."
        return ConnectionReadinessView(
            id=row.id,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            provider_type=row.provider_type,
            credential_id=row.credential_id,
            lifecycle_state=row.lifecycle_state,
            provider_mode=row.provider_mode,
            capabilities=row.capabilities or {},
            health_score=row.health_score,
            failure_reason=row.failure_reason,
            last_validated_at=row.last_validated_at,
            last_successful_at=row.last_successful_at,
            reauth_required=row.reauth_required,
            validation_metadata=row.validation_metadata or {},
            feature_impact=impact,
            remediation=remediation,
        )

    async def validate_connection(
        self, user: User, org_context: OrgContext, registry_id: str,
    ) -> ValidateResponse:
        organization_id = self._ensure_write(user, org_context)
        row = await self._get_registry(organization_id, registry_id)
        previous_state = row.lifecycle_state
        row.lifecycle_state = "VALIDATING"
        await self.session.flush()

        await emit_event(
            self.session, DomainEventType.INTEGRATION_VALIDATION_STARTED,
            organization_id=organization_id,
            payload={"registry_id": row.id, "provider_type": row.provider_type},
        )

        started = time.monotonic()
        secret = await self._resolve_secret(row, user, org_context)
        probe_result = await self._run_probe(row, secret=secret)
        latency_ms = int((time.monotonic() - started) * 1000)

        status = probe_result.get("connection_status", VStatus.FAILED)
        lifecycle, mode = map_verification_status(status)
        connected = status == VStatus.CONNECTED
        partial = status == VStatus.PARTIAL
        permissions = probe_result.get("permissions") or []
        caps = build_capability_matrix(row.provider_type, permissions)
        score = health_score_from_result(connected=connected, partial=partial, capabilities=caps)

        if status == VStatus.UNAUTHORIZED:
            row.reauth_required = True
            lifecycle = "REAUTH_REQUIRED"

        consecutive = 0 if connected or partial else row.consecutive_failures + 1
        threshold = getattr(settings, "INTEGRATION_HEALTH_FAILURE_THRESHOLD", 3)
        new_state = should_transition_state(
            previous_state, lifecycle, consecutive_failures=consecutive, threshold=threshold,
        )
        if status != VStatus.CONNECTED and lifecycle == "CONNECTED":
            new_state = previous_state if previous_state in ("CONNECTED", "DEGRADED") else lifecycle

        row.lifecycle_state = new_state
        row.provider_mode = probe_result.get("provider_mode") or mode
        row.capabilities = caps
        row.health_score = score
        row.failure_reason = _redact_failure(probe_result.get("errors"))
        row.consecutive_failures = consecutive
        row.last_validated_at = datetime.now(UTC)
        if connected or partial:
            row.last_successful_at = datetime.now(UTC)
            row.reauth_required = status == VStatus.UNAUTHORIZED
        row.validation_metadata = {
            "permissions": permissions,
            "provider_identity": probe_result.get("provider_identity") or {},
            "warnings": probe_result.get("warnings") or [],
        }

        hist = IntHealthHistory(
            organization_id=organization_id,
            registry_id=row.id,
            previous_state=previous_state,
            new_state=new_state,
            probe_result={"status": status, "capabilities": caps, "latency_ms": latency_ms},
            latency_ms=latency_ms,
        )
        self.session.add(hist)

        await self._emit_transition(organization_id, row, previous_state, new_state)
        await self._record_validation_metrics(row.provider_type, status, latency_ms / 1000.0)

        guidance = self._guidance_for_state(new_state, row.failure_reason)
        await self.audit.log(
            action="integration.validate",
            resource_type="int_connection_registry",
            resource_id=row.id,
            user_id=user.id,
            organization_id=organization_id,
            details={"state": new_state, "provider_mode": row.provider_mode},
        )
        await self.session.flush()

        if (connected or partial) and row.resource_type == "marketplace":
            await self._auto_sync_marketplace(user, org_context, row)

        return ValidateResponse(
            connection_id=row.id,
            lifecycle_state=new_state,
            provider_mode=row.provider_mode,
            health_score=score,
            capabilities=caps,
            failure_reason=row.failure_reason,
            latency_ms=latency_ms,
            guidance=guidance,
        )

    async def _auto_sync_marketplace(
        self, user: User, org_context: OrgContext, row: IntConnectionRegistry,
    ) -> None:
        key = (row.provider_type or "").upper()
        if not row.resource_id:
            return
        try:
            if supports_pipeline_sync(key):
                await IntegrationSyncService(self.session).sync_connection(
                    user, org_context, row.resource_id, sync_runs=True,
                )
            else:
                conn = await self.connections.get_for_org(row.resource_id, row.organization_id)
                if conn:
                    await self.connections.update(conn, last_sync_at=datetime.now(UTC))
        except Exception as exc:  # noqa: BLE001
            logger.info(
                "integration_validate_auto_sync_skipped",
                registry_id=row.id, provider=key, error=type(exc).__name__,
            )

    async def _resolve_secret(
        self, row: IntConnectionRegistry, user: User, org_context: OrgContext,
    ) -> dict | None:
        if not row.credential_id:
            return None
        try:
            _, secret = await self.secrets.resolve_secret(
                row.credential_id, user=user, org_context=org_context, reason="integration_validate", audit=False,
            )
            return secret
        except Exception as exc:  # noqa: BLE001
            logger.warning("integration_probe_credential_failed", registry_id=row.id, error=str(exc))
            return None

    async def _run_probe(self, row: IntConnectionRegistry, *, secret: dict | None = None) -> dict:
        if row.credential_id and secret is None:
            return {
                "connection_status": VStatus.FAILED,
                "permissions": [],
                "errors": ["Credential could not be resolved."],
            }

        ptype = row.provider_type.upper()
        if row.resource_type == "marketplace" and secret:
            conn = await self.connections.get_for_org(row.resource_id, row.organization_id)
            key = conn.integration_key if conn else ptype.lower()
            return await probe_marketplace_connection(key, secret)
        if ptype in ("KUBERNETES", "K8S") and secret:
            return await probe_kubernetes(secret)
        if ptype in ("TRIVY", "GITLEAKS", "SEMGREP", "CHECKOV"):
            return probe_security_binary(ptype)
        if ptype in ("PROMETHEUS", "LOKI", "TEMPO", "JAEGER", "METRICS", "GRAFANA"):
            meta = row.validation_metadata or {}
            return probe_observability(ptype, meta)
        if ptype in ("SLACK", "TEAMS", "EMAIL", "SMTP"):
            return probe_notification(ptype, secret or {})
        return {
            "connection_status": VStatus.TIMEOUT,
            "permissions": [],
            "provider_mode": "offline",
            "warnings": ["No live probe configured for this provider type."],
        }

    async def _emit_transition(
        self, organization_id: str, row: IntConnectionRegistry, previous: str, new: str,
    ) -> None:
        if previous == new:
            return
        event_map = {
            "CONNECTED": DomainEventType.INTEGRATION_CONNECTED,
            "DEGRADED": DomainEventType.INTEGRATION_DEGRADED,
            "FAILED": DomainEventType.INTEGRATION_FAILED,
            "EXPIRED": DomainEventType.INTEGRATION_EXPIRED,
            "REAUTH_REQUIRED": DomainEventType.INTEGRATION_REAUTH_REQUIRED,
        }
        if new in event_map:
            await emit_event(
                self.session, event_map[new],
                organization_id=organization_id,
                payload={"registry_id": row.id, "previous_state": previous},
            )
        if previous in ("FAILED", "DEGRADED") and new == "CONNECTED":
            await emit_event(
                self.session, DomainEventType.INTEGRATION_RECOVERED,
                organization_id=organization_id,
                payload={"registry_id": row.id},
            )

    @staticmethod
    def _guidance_for_state(state: str, failure_reason: str | None) -> str:
        guides = {
            "CONNECTED": "Connection validated successfully.",
            "DEGRADED": "Partial connectivity — review capability gaps.",
            "FAILED": failure_reason or "Validation failed; check credentials and network.",
            "REAUTH_REQUIRED": "Credentials rejected — rotate and re-validate.",
            "EXPIRED": "Credentials expired — renew before live operations.",
        }
        return guides.get(state, "Run validation to refresh connection health.")

    async def get_capabilities(
        self, user: User, org_context: OrgContext, registry_id: str,
    ) -> CapabilitiesView:
        organization_id = self._ensure_read(user, org_context)
        row = await self._get_registry(organization_id, registry_id)
        write_check = enforce_write_allowed(
            row.capabilities or {}, provider_mode=row.provider_mode, lifecycle_state=row.lifecycle_state,
        )
        return CapabilitiesView(
            connection_id=row.id,
            capabilities=row.capabilities or {},
            provider_mode=row.provider_mode,
            lifecycle_state=row.lifecycle_state,
            write_allowed=write_check["allowed"],
        )

    async def get_health(self, user: User, org_context: OrgContext, registry_id: str) -> HealthView:
        organization_id = self._ensure_read(user, org_context)
        row = await self._get_registry(organization_id, registry_id)
        return HealthView(
            connection_id=row.id,
            lifecycle_state=row.lifecycle_state,
            provider_mode=row.provider_mode,
            health_score=row.health_score,
            consecutive_failures=row.consecutive_failures,
            last_validated_at=row.last_validated_at,
            last_successful_at=row.last_successful_at,
            failure_reason=row.failure_reason,
            reauth_required=row.reauth_required,
        )

    async def get_history(
        self, user: User, org_context: OrgContext, registry_id: str,
    ) -> list[HealthHistoryEntry]:
        organization_id = self._ensure_read(user, org_context)
        await self._get_registry(organization_id, registry_id)
        entries = await self.history.list_for_registry(registry_id)
        return [
            HealthHistoryEntry(
                id=e.id,
                previous_state=e.previous_state,
                new_state=e.new_state,
                probe_result=e.probe_result or {},
                latency_ms=e.latency_ms,
                created_at=e.created_at,
            )
            for e in entries
        ]

    async def get_expiry(
        self, user: User, org_context: OrgContext, registry_id: str,
    ) -> list[ExpiryReminderView]:
        organization_id = self._ensure_read(user, org_context)
        await self._get_registry(organization_id, registry_id)
        reminders = await self.expiry.list_for_registry(registry_id)
        return [
            ExpiryReminderView(
                id=r.id,
                warning_level=r.warning_level,
                expires_at=r.expires_at,
                acknowledged=r.acknowledged,
                snoozed_until=r.snoozed_until,
                metadata=r.reminder_metadata or {},
            )
            for r in reminders
        ]

    async def acknowledge_expiry(
        self, user: User, org_context: OrgContext, registry_id: str, reminder_id: str | None = None,
    ) -> dict:
        organization_id = self._ensure_write(user, org_context)
        await self._get_registry(organization_id, registry_id)
        reminders = await self.expiry.list_for_registry(registry_id)
        updated = 0
        for r in reminders:
            if reminder_id and r.id != reminder_id:
                continue
            r.acknowledged = True
            updated += 1
        await self.session.flush()
        return {"acknowledged": updated}

    async def snooze_expiry(
        self, user: User, org_context: OrgContext, registry_id: str,
        *, reminder_id: str | None = None, days: int = 7,
    ) -> dict:
        organization_id = self._ensure_write(user, org_context)
        await self._get_registry(organization_id, registry_id)
        until = datetime.now(UTC) + timedelta(days=days)
        reminders = await self.expiry.list_for_registry(registry_id)
        updated = 0
        for r in reminders:
            if reminder_id and r.id != reminder_id:
                continue
            r.snoozed_until = until
            updated += 1
        await self.session.flush()
        return {"snoozed_until": until.isoformat(), "count": updated}

    async def get_dashboard(self, user: User, org_context: OrgContext) -> IntegrationDashboard:
        organization_id = self._ensure_read(user, org_context)
        await self.sync_registry(organization_id)
        rows = await self.registry.list_for_org(organization_id)
        last_val = max((r.last_validated_at for r in rows if r.last_validated_at), default=None)
        gaps: list[dict] = []
        for row in rows:
            caps = row.capabilities or {}
            missing = [k for k, v in caps.items() if not v]
            if missing and row.lifecycle_state in ("CONNECTED", "DEGRADED"):
                gaps.append({"connection_id": row.id, "provider": row.provider_type, "missing": missing})
        pending = await self.expiry.list_pending_for_org(organization_id)
        upcoming = [
            {"registry_id": r.registry_id, "warning_level": r.warning_level, "expires_at": str(r.expires_at)}
            for r in pending if not r.snoozed_until or r.snoozed_until < datetime.now(UTC)
        ]
        features: set[str] = set()
        for row in rows:
            if row.lifecycle_state not in ("CONNECTED", "DEGRADED"):
                features.update(FEATURE_IMPACT.get(row.provider_type, []))
        hints = []
        if any(r.lifecycle_state == "REAUTH_REQUIRED" for r in rows):
            hints.append("One or more integrations require reauthentication.")
        if any(r.lifecycle_state == "EXPIRED" for r in rows):
            hints.append("Expired credentials block live operations.")
        return IntegrationDashboard(
            total=len(rows),
            connected=sum(1 for r in rows if r.lifecycle_state == "CONNECTED"),
            degraded=sum(1 for r in rows if r.lifecycle_state == "DEGRADED"),
            failed=sum(1 for r in rows if r.lifecycle_state == "FAILED"),
            expired=sum(1 for r in rows if r.lifecycle_state == "EXPIRED"),
            reauth_required=sum(1 for r in rows if r.lifecycle_state == "REAUTH_REQUIRED"),
            last_validation=last_val,
            capability_gaps=gaps,
            upcoming_expiry=upcoming,
            affected_features=sorted(features),
            remediation_hints=hints,
        )

    async def test_notification(
        self, user: User, org_context: OrgContext, *, channel: str = "slack", dry_run: bool = True,
    ) -> dict:
        organization_id = self._ensure_write(user, org_context)
        normalized = (channel or "slack").lower()
        if normalized not in ("slack", "teams", "email"):
            raise ValidationError(f"Unsupported test channel: {channel}")
        if dry_run:
            return {
                "sent": False,
                "simulated": True,
                "channel": normalized,
                "message": "Dry-run validation only — set dry_run=false to send a live test.",
            }
        from app.services.incident_notifications import (
            send_slack_text,
            send_teams_text,
            send_email_summary,
        )
        from app.services.notification_channels import OrgNotificationChannelService

        channels = OrgNotificationChannelService(self.session)
        body = (
            f"Test notification from Nexora ({normalized}). "
            "If you received this, outbound delivery is configured."
        )
        simulated = False
        try:
            if normalized == "slack":
                webhook = await channels.resolve_slack_webhook(organization_id)
                if not webhook:
                    simulated = True
                else:
                    await send_slack_text(body, webhook=webhook)
            elif normalized == "teams":
                webhook = await channels.resolve_teams_webhook(organization_id)
                if not webhook:
                    simulated = True
                else:
                    await send_teams_text(body, webhook=webhook)
            else:
                await send_email_summary("INFO", "Nexora test notification")
                simulated = True
        except Exception as exc:  # noqa: BLE001
            return {
                "sent": False,
                "simulated": False,
                "channel": normalized,
                "message": str(exc)[:200],
            }
        return {
            "sent": not simulated,
            "simulated": simulated,
            "channel": normalized,
            "message": "Delivered" if not simulated else "Simulated (configure org webhook in Settings → Notifications)",
        }

    async def run_preflight(
        self,
        *,
        organization_id: str,
        registry_id: str,
        required_capabilities: list[str],
        environment_id: str | None = None,
        idempotency_key: str,
        approval_satisfied: bool = True,
        explicit_simulation: bool = False,
        operation_type: str = "live_mutation",
    ) -> dict:
        row = await self._get_registry(organization_id, registry_id)
        registry = {
            "organization_id": row.organization_id,
            "lifecycle_state": row.lifecycle_state,
            "provider_mode": row.provider_mode,
            "capabilities": row.capabilities,
            "credential_id": row.credential_id,
            "reauth_required": row.reauth_required,
        }
        result = preflight_live_operation(
            registry=registry,
            required_capabilities=required_capabilities,
            environment_id=environment_id,
            organization_id=organization_id,
            idempotency_key=idempotency_key,
            approval_satisfied=approval_satisfied,
            explicit_simulation=explicit_simulation,
        )
        outcome = "allowed" if result["allowed"] else "blocked"
        ev = IntLiveEvidence(
            organization_id=organization_id,
            registry_id=row.id,
            operation_type=operation_type,
            correlation_id=idempotency_key,
            outcome=outcome,
            blocked_reason=result.get("reason"),
            evidence=build_live_evidence(
                correlation_id=idempotency_key,
                resource_ids={"registry_id": row.id},
                outcome=outcome,
            ),
            verification={"simulated": result.get("simulated", False)},
        )
        self.session.add(ev)
        if not result["allowed"]:
            await emit_event(
                self.session, DomainEventType.LIVE_OPERATION_BLOCKED,
                organization_id=organization_id,
                payload={"registry_id": row.id, "reason": result.get("reason")},
            )
            await self._record_live_operation_metric("blocked")
        else:
            await emit_event(
                self.session, DomainEventType.LIVE_OPERATION_EXECUTED,
                organization_id=organization_id,
                payload={"registry_id": row.id, "simulated": result.get("simulated")},
            )
            await self._record_live_operation_metric("executed")
        await self.session.flush()
        return result

    async def list_observability_for_org(self, organization_id: str) -> list[dict]:
        rows = await self.registry.list_for_org(organization_id)
        return [
            {
                "kind": r.provider_type,
                "provider_mode": r.provider_mode,
                "capabilities": r.capabilities or {},
                "lifecycle_state": r.lifecycle_state,
            }
            for r in rows
            if r.resource_type == "observability" or r.provider_type in (
                "PROMETHEUS", "LOKI", "TEMPO", "JAEGER", "METRICS",
            )
        ]

    async def process_expiry_warnings(self, organization_id: str) -> int:
        """Create metadata-only expiry reminders from validation metadata."""
        rows = await self.registry.list_for_org(organization_id)
        created = 0
        now = datetime.now(UTC)
        for row in rows:
            meta = row.validation_metadata or {}
            expires_at = meta.get("expires_at")
            if not expires_at:
                continue
            if isinstance(expires_at, str):
                try:
                    expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                except ValueError:
                    continue
            days_left = (expires_at - now).days
            for level in EXPIRY_WINDOWS:
                if days_left <= EXPIRY_DAYS[level]:
                    existing = await self.expiry.list_for_registry(row.id)
                    if any(e.warning_level == level and not e.acknowledged for e in existing):
                        continue
                    reminder = IntExpiryReminder(
                        organization_id=organization_id,
                        registry_id=row.id,
                        expires_at=expires_at,
                        warning_level=level,
                        reminder_metadata={"provider_type": row.provider_type},
                    )
                    self.session.add(reminder)
                    created += 1
                    await emit_event(
                        self.session, DomainEventType.INTEGRATION_EXPIRY_WARNING,
                        organization_id=organization_id,
                        payload={"registry_id": row.id, "warning_level": level},
                    )
        if created:
            await self.session.flush()
        return created

    async def _record_validation_metrics(self, provider: str, status: str, duration: float) -> None:
        try:
            from app.observability import metrics
            metrics.record_integration_validation(provider, status, duration)
        except Exception:  # pragma: no cover
            pass

    async def _record_live_operation_metric(self, outcome: str) -> None:
        try:
            from app.observability import metrics
            metrics.record_live_operation(outcome)
        except Exception:  # pragma: no cover
            pass

    @staticmethod
    def registry_dict(row: IntConnectionRegistry) -> dict:
        return {
            "id": row.id,
            "organization_id": row.organization_id,
            "lifecycle_state": row.lifecycle_state,
            "provider_mode": row.provider_mode,
            "capabilities": row.capabilities or {},
            "credential_id": row.credential_id,
            "reauth_required": row.reauth_required,
            "provider_type": row.provider_type,
        }
