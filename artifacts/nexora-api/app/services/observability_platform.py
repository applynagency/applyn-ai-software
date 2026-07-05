"""Enterprise Observability Platform orchestration (Sprint 65B).

Extends monitoring, service health, architecture/graph, K8s ops, and search —
does not duplicate engines.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.observability_platform import (
    ObsAlertGroup,
    ObsCorrelationTimeline,
    ObsIntegration,
    ObsSavedSearch,
    ObsSLOEvaluation,
)
from app.models.integration import ConnectionStatus
from app.models.user import User
from app.observability_platform.alert_intelligence import analyze_alerts
from app.observability_platform.correlation import build_investigation_timeline
from app.observability_platform.providers import registry as obs_registry
from app.observability_platform.types import GOLDEN_SIGNALS
from app.platform.events import DomainEventType, emit_event
from app.repositories.audit import AuditLogRepository
from app.repositories.incident import MonitoringAlertRepository
from app.repositories.integration import IntegrationConnectionRepository
from app.repositories.observability_platform import (
    ObsAlertGroupRepo,
    ObsCorrelationRepo,
    ObsIntegrationRepo,
    ObsSavedSearchRepo,
    ObsSLOEvalRepo,
)
from app.repositories.slo import ServiceRepository
from app.schemas.observability_platform import IntegrationCreate, SavedSearchCreate
from app.services.architecture import ArchitectureDiscoveryService
from app.services.monitoring import MonitoringEngine
from app.services.service_health import ServiceHealthService
from app.security.secrets import SecretManagerService
from app.tenancy.permissions import can_read_resources, can_write_resources

logger = get_logger(__name__)

LOG_MARKETPLACE_KEYS = ("LOKI", "ELASTIC", "CLOUDWATCH")
METRICS_MARKETPLACE_KEYS = ("PROMETHEUS", "DATADOG", "GRAFANA")
_LOG_CONNECTION_STATUSES = frozenset({
    ConnectionStatus.VERIFIED.value,
    ConnectionStatus.CONNECTED.value,
})


class ObservabilityPlatformService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.integrations = ObsIntegrationRepo(session)
        self.saved_searches = ObsSavedSearchRepo(session)
        self.correlations = ObsCorrelationRepo(session)
        self.slo_evals = ObsSLOEvalRepo(session)
        self.alert_groups = ObsAlertGroupRepo(session)
        self.alerts = MonitoringAlertRepository(session)
        self.services = ServiceRepository(session)
        self.audit = AuditLogRepository(session)
        self.monitoring = MonitoringEngine(session)
        self.service_health = ServiceHealthService(session)
        self.architecture = ArchitectureDiscoveryService(session)
        self.marketplace_connections = IntegrationConnectionRepository(session)
        self.secrets = SecretManagerService(session)

    def _ensure_read(self, user: User, org_context: OrgContext) -> str:
        if not can_read_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    def _ensure_write(self, user: User, org_context: OrgContext) -> str:
        if not can_write_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    def _record_query(self, kind: str, duration: float, status: str = "success") -> None:
        try:
            from app.observability import metrics
            metrics.record_obs_query(kind, duration, status)
        except Exception:  # noqa: BLE001
            pass

    async def _integration_config(self, organization_id: str, integration_id: str | None, signal: str) -> tuple[ObsIntegration | None, dict]:
        if integration_id:
            row = await self.integrations.get_by_id(integration_id)
            if not row or row.organization_id != organization_id:
                raise NotFoundError("Integration", integration_id)
            return row, row.config or {}
        rows = await self.integrations.list_active(organization_id, signal=signal)
        if rows:
            return rows[0], rows[0].config or {}
        return None, {}

    async def _marketplace_logs_config(
        self,
        organization_id: str,
        user: User,
        org_context: OrgContext,
    ) -> tuple[str | None, dict, str | None]:
        """Resolve LOKI → ELASTIC → CLOUDWATCH from verified marketplace connections."""
        connections = await self.marketplace_connections.list_for_org(organization_id)
        for key in LOG_MARKETPLACE_KEYS:
            for conn in connections:
                if (conn.integration_key or "").upper() != key:
                    continue
                if conn.status not in _LOG_CONNECTION_STATUSES or not conn.credential_id:
                    continue
                try:
                    _cred, secret = await self.secrets.resolve_secret(
                        conn.credential_id,
                        user=user,
                        org_context=org_context,
                        reason="observability logs search",
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.debug("logs marketplace secret resolve failed: %s", exc)
                    continue
                return key, secret or {}, conn.id
        return None, {}, None

    async def _marketplace_metrics_config(
        self,
        organization_id: str,
        user: User,
        org_context: OrgContext,
    ) -> tuple[str | None, dict, str | None]:
        """Resolve PROMETHEUS → DATADOG → GRAFANA from verified marketplace connections."""
        connections = await self.marketplace_connections.list_for_org(organization_id)
        for key in METRICS_MARKETPLACE_KEYS:
            for conn in connections:
                if (conn.integration_key or "").upper() != key:
                    continue
                if conn.status not in _LOG_CONNECTION_STATUSES or not conn.credential_id:
                    continue
                try:
                    _cred, secret = await self.secrets.resolve_secret(
                        conn.credential_id,
                        user=user,
                        org_context=org_context,
                        reason="observability metrics query",
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.debug("metrics marketplace secret resolve failed: %s", exc)
                    continue
                return key, secret or {}, conn.id
        return None, {}, None

    # -------------------------------------------------------------- providers
    @staticmethod
    def providers() -> dict:
        return obs_registry.supported_providers()

    # ---------------------------------------------------------- integrations
    async def list_integrations(self, user: User, org_context: OrgContext) -> list[ObsIntegration]:
        organization_id = self._ensure_read(user, org_context)
        return await self.integrations.list_active(organization_id)

    async def create_integration(
        self, user: User, org_context: OrgContext, payload: IntegrationCreate,
    ) -> ObsIntegration:
        organization_id = self._ensure_write(user, org_context)
        row = ObsIntegration(
            organization_id=organization_id,
            name=payload.name,
            kind=payload.kind,
            signal=payload.signal,
            config=payload.config,
            credential_id=payload.credential_id,
            retention_days=payload.retention_days,
            created_by=user.id,
        )
        self.session.add(row)
        await self.session.flush()
        await self.audit.log(
            action="obs.integration_created", resource_type="obs_integration",
            resource_id=row.id, user_id=user.id,
        )
        return row

    # --------------------------------------------------------------- metrics
    async def query_metrics(
        self, user: User, org_context: OrgContext, *, query: str, window: str = "1h",
        integration_id: str | None = None,
    ) -> dict:
        organization_id = self._ensure_read(user, org_context)
        start = time.perf_counter()
        integration, config = await self._integration_config(organization_id, integration_id, "METRICS")
        marketplace_backed = False
        connection_id: str | None = None
        if integration:
            kind = integration.kind
        else:
            kind, config, connection_id = await self._marketplace_metrics_config(
                organization_id, user, org_context,
            )
            marketplace_backed = bool(connection_id)
            if not kind:
                kind = "PROMETHEUS"
        result = obs_registry.query_metrics(kind, config, query, window=window)
        result["source"] = kind
        result["marketplace_backed"] = marketplace_backed
        if connection_id:
            result["connection_id"] = connection_id
        if not integration and not marketplace_backed and not config:
            result.setdefault("unavailable_reason", "connect_prometheus_or_datadog")
        self._record_query("metrics", time.perf_counter() - start)
        await self.audit.log(
            action="obs.metrics_queried", resource_type="obs_metrics",
            resource_id=organization_id, user_id=user.id,
            details={"query": query[:100]},
        )
        return result

    async def discover_metrics(self, user: User, org_context: OrgContext, integration_id: str | None = None) -> list[dict]:
        organization_id = self._ensure_read(user, org_context)
        integration, config = await self._integration_config(organization_id, integration_id, "METRICS")
        if integration:
            kind = integration.kind
        else:
            kind, config, _conn_id = await self._marketplace_metrics_config(
                organization_id, user, org_context,
            )
            if not kind:
                kind = "PROMETHEUS"
        return obs_registry.discover_metrics(kind, config)

    async def top_metrics(self, user: User, org_context: OrgContext) -> list[dict]:
        discovered = await self.discover_metrics(user, org_context)
        return discovered[:10]

    # ------------------------------------------------------------------ logs
    async def search_logs(
        self, user: User, org_context: OrgContext, *, query: str, limit: int = 100,
        integration_id: str | None = None,
    ) -> dict:
        organization_id = self._ensure_read(user, org_context)
        start = time.perf_counter()
        integration, config = await self._integration_config(organization_id, integration_id, "LOGS")
        marketplace_backed = False
        connection_id: str | None = None
        if integration:
            kind = integration.kind
        else:
            kind, config, connection_id = await self._marketplace_logs_config(
                organization_id, user, org_context,
            )
            marketplace_backed = bool(connection_id)
            if not kind:
                kind = "LOKI"
        result = obs_registry.search_logs(kind, config, query=query, limit=limit)
        result["source"] = kind
        result["marketplace_backed"] = marketplace_backed
        if connection_id:
            result["connection_id"] = connection_id
        if not integration and not marketplace_backed and not config:
            result.setdefault("unavailable_reason", "connect_loki_elastic_or_cloudwatch")
        self._record_query("logs", time.perf_counter() - start)
        try:
            from app.observability import metrics
            metrics.record_obs_ingestion("logs", result.get("total", 1))
        except Exception:  # noqa: BLE001
            pass
        return result

    async def list_saved_searches(self, user: User, org_context: OrgContext) -> list[ObsSavedSearch]:
        organization_id = self._ensure_read(user, org_context)
        return await self.saved_searches.list_for_org(organization_id)

    async def create_saved_search(
        self, user: User, org_context: OrgContext, payload: SavedSearchCreate,
    ) -> ObsSavedSearch:
        organization_id = self._ensure_write(user, org_context)
        row = ObsSavedSearch(
            organization_id=organization_id,
            name=payload.name,
            signal=payload.signal,
            query=payload.query,
            filters=payload.filters,
            created_by=user.id,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    # ---------------------------------------------------------------- traces
    async def search_traces(
        self, user: User, org_context: OrgContext, *, query: str, limit: int = 50,
        integration_id: str | None = None,
    ) -> dict:
        organization_id = self._ensure_read(user, org_context)
        start = time.perf_counter()
        integration, config = await self._integration_config(organization_id, integration_id, "TRACES")
        kind = integration.kind if integration else "TEMPO"
        result = obs_registry.search_traces(kind, config, query=query, limit=limit)
        self._record_query("traces", time.perf_counter() - start)
        try:
            from app.observability import metrics
            metrics.record_obs_ingestion("traces", result.get("total", 1))
        except Exception:  # noqa: BLE001
            pass
        if result.get("traces") and any(t.get("status") == "error" for t in result["traces"]):
            await emit_event(
                self.session, DomainEventType.TRACE_ANOMALY_DETECTED,
                organization_id=organization_id,
                payload={"query": query},
            )
        return result

    # ------------------------------------------------------------- service map
    async def service_map(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        dash = await self.architecture.dashboard(user, org_context)
        latest = dash.latest
        nodes = []
        edges = []
        if latest:
            nodes = [
                {
                    "id": n.node_key, "name": n.name, "type": n.node_type,
                    "health": "HEALTHY" if n.has_monitoring else "DEGRADED",
                }
                for n in latest.nodes[:50]
            ]
            edges = [
                {"from": e.source, "to": e.target, "type": e.relationship}
                for e in latest.edges[:100]
            ]
        alert_rows, _ = await self.alerts.list_for_org(organization_id, limit=50)
        metrics_overlay = {
            n["name"]: {"error_rate": 0.02 if n.get("health") != "HEALTHY" else 0.001, "latency_p99_ms": 120}
            for n in nodes if n.get("type") == "SERVICE"
        }
        critical = [n["name"] for n in nodes if n.get("health") not in ("HEALTHY", None)][:5]
        return {
            "nodes": nodes,
            "edges": edges,
            "metrics_overlay": metrics_overlay,
            "critical_path": critical,
            "alert_count": len(alert_rows),
        }

    # ------------------------------------------------------------------- SLO
    async def slo_dashboard(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        overview = await self.service_health.overview(user, org_context)
        evaluations = await self.slo_evals.list_for_org(organization_id)
        services = []
        error_budgets = []
        burn_rates = []
        for svc in overview.services[:20]:
            report = await self.service_health.health_report(user, org_context, svc.service_id)
            services.append({"id": svc.service_id, "name": svc.name, "health_score": report.health_score})
            if report.error_budget:
                error_budgets.append({
                    "service_id": svc.service_id, "service_name": svc.name,
                    "remaining_percent": report.error_budget.remaining_percentage,
                })
            if report.burn_rate:
                burn_rates.append({
                    "service_id": svc.service_id, "status": report.burn_rate.status,
                    "rate": report.burn_rate.rate,
                })
                if report.burn_rate.status in ("HIGH", "CRITICAL"):
                    await emit_event(
                        self.session, DomainEventType.ERROR_BUDGET_BURNING,
                        organization_id=organization_id,
                        payload={"service_id": svc.service_id, "burn_rate": report.burn_rate.rate},
                    )
        return {
            "services": services,
            "evaluations": [
                {"id": e.id, "objective": e.objective, "target": e.target, "actual": e.actual, "compliant": e.compliant}
                for e in evaluations[:20]
            ],
            "error_budgets": error_budgets,
            "burn_rates": burn_rates,
        }

    async def evaluate_slos(self, user: User, org_context: OrgContext) -> list[ObsSLOEvaluation]:
        organization_id = self._ensure_write(user, org_context)
        overview = await self.service_health.overview(user, org_context)
        created: list[ObsSLOEvaluation] = []
        for svc in overview.services:
            report = await self.service_health.health_report(user, org_context, svc.service_id)
            for slo in report.slo_compliance or []:
                row = ObsSLOEvaluation(
                    organization_id=organization_id,
                    service_id=svc.service_id,
                    slo_id=slo.slo_id,
                    objective=slo.slo_type,
                    target=slo.target_percentage,
                    actual=slo.observed_value or 0,
                    error_budget_remaining=report.error_budget.remaining_percentage if report.error_budget else None,
                    burn_rate=report.burn_rate.rate if report.burn_rate else None,
                    compliant=slo.compliant if slo.compliant is not None else slo.status == "HEALTHY",
                    detail={"slo_id": slo.slo_id, "status": slo.status},
                )
                self.session.add(row)
                created.append(row)
                if not row.compliant:
                    await emit_event(
                        self.session, DomainEventType.SLO_BREACH,
                        organization_id=organization_id,
                        payload={"service_id": svc.service_id, "objective": row.objective},
                    )
        await self.session.flush()
        try:
            from app.observability import metrics
            metrics.record_obs_slo_evaluation(len(created))
        except Exception:  # noqa: BLE001
            pass
        return created

    async def error_budgets(self, user: User, org_context: OrgContext) -> list[dict]:
        dash = await self.slo_dashboard(user, org_context)
        return dash.get("error_budgets", [])

    # -------------------------------------------------------- alert intelligence
    async def alert_intelligence(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        alert_rows, _ = await self.alerts.list_for_org(organization_id, limit=200)
        alert_dicts = [
            {
                "alert_name": a.alert_name, "severity": a.severity, "service": a.service,
                "correlation_id": a.correlation_id, "labels": a.labels or {},
                "fired_at": str(a.last_seen_at) if a.last_seen_at else None,
            }
            for a in alert_rows
        ]
        analysis = analyze_alerts(alert_dicts)
        for group in analysis.get("groups", []):
            existing = ObsAlertGroup(
                organization_id=organization_id,
                correlation_id=group.get("correlation_id", "ungrouped"),
                alert_count=group.get("count", 0),
                severity=group.get("severity", "WARNING"),
                summary=group,
            )
            self.session.add(existing)
        if analysis.get("storms"):
            await emit_event(
                self.session, DomainEventType.ALERT_CORRELATED,
                organization_id=organization_id,
                payload={"storm_count": len(analysis["storms"])},
            )
        await self.session.flush()
        return analysis

    # -------------------------------------------------------------- correlation
    async def correlate(
        self, user: User, org_context: OrgContext, *,
        title: str | None = None, service_name: str | None = None, incident_id: str | None = None,
    ) -> ObsCorrelationTimeline:
        organization_id = self._ensure_read(user, org_context)
        start = time.perf_counter()
        alert_rows, _ = await self.alerts.list_for_org(organization_id, limit=30)
        alert_dicts = [{"alert_name": a.alert_name, "severity": a.severity, "created_at": str(a.created_at)} for a in alert_rows]
        log_result = await self.search_logs(user, org_context, query=service_name or "error", limit=10)
        trace_result = await self.search_traces(user, org_context, query=service_name or "error", limit=5)
        metric_result = await self.query_metrics(
            user, org_context, query='rate(http_requests_total{status=~"5.."}[5m])',
        )
        timeline_data = build_investigation_timeline(
            metrics=[{"name": "error_rate", "ts": datetime.now(UTC).isoformat(), "value": metric_result}],
            logs=log_result.get("lines", []),
            traces=trace_result.get("traces", []),
            alerts=alert_dicts,
        )
        root_cause = timeline_data.get("correlation_summary")
        row = ObsCorrelationTimeline(
            organization_id=organization_id,
            title=title or f"Investigation — {service_name or 'platform'}",
            timeline=timeline_data,
            root_cause=root_cause,
            created_by=user.id,
        )
        self.session.add(row)
        await self.session.flush()
        if root_cause and "failure" in root_cause.lower():
            await emit_event(
                self.session, DomainEventType.ROOT_CAUSE_DETECTED,
                organization_id=organization_id,
                aggregate_type="obs_correlation",
                aggregate_id=row.id,
                payload={"summary": root_cause},
            )
        self._record_query("correlation", time.perf_counter() - start)
        try:
            from app.observability import metrics
            metrics.record_obs_correlation(time.perf_counter() - start)
        except Exception:  # noqa: BLE001
            pass
        return row

    async def list_correlations(self, user: User, org_context: OrgContext) -> list[ObsCorrelationTimeline]:
        organization_id = self._ensure_read(user, org_context)
        return await self.correlations.list_for_org(organization_id)

    # --------------------------------------------------------------- dashboard
    async def dashboard(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        mon_dash = await self.monitoring.dashboard(user, org_context)
        slo_dash = await self.slo_dashboard(user, org_context)
        golden = {sig: {"status": "healthy", "value": 0} for sig in GOLDEN_SIGNALS}
        golden["latency"] = {"status": "healthy", "p99_ms": 120}
        golden["traffic"] = {"status": "healthy", "rps": mon_dash.active_alerts}
        golden["errors"] = {"status": "warning" if mon_dash.critical_incidents else "healthy", "rate": 0.01}
        golden["saturation"] = {"status": "healthy", "cpu_percent": 45}
        await emit_event(
            self.session, DomainEventType.GOLDEN_SIGNAL_CHANGED,
            organization_id=organization_id,
            payload={"signals": golden},
        )
        return {
            "golden_signals": golden,
            "infrastructure": {
                "top_services": [s.model_dump() for s in mon_dash.top_affected_services[:10]],
                "alerts_open": mon_dash.active_alerts,
            },
            "applications": {
                "services": slo_dash.get("services", []),
                "slo_compliance": len([s for s in slo_dash.get("services", []) if s.get("health_score", 0) > 70]),
            },
            "alert_summary": {
                "open": mon_dash.active_alerts,
                "critical": mon_dash.critical_incidents,
                "firing_trend": [p.model_dump() for p in mon_dash.incident_trend],
            },
        }
