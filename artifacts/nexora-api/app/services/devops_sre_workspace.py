"""DevOps & SRE workspace orchestration (Sprint 63C).

Aggregates existing platform services into a single daily-operations surface.
Does not duplicate engines — every signal is sourced from an existing service.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.database.base import utcnow
from app.delivery.types import DeliveryStatus
from app.models.job import JobStatus
from app.models.ops_workspace import (
    WorkspaceAutomationSuggestion,
    WorkspaceCalendarEvent,
    WorkspaceDailyBriefing,
    WorkspaceMaintenanceWindow,
    WorkspaceShiftHandover,
)
from app.models.sre import SREAIRecommendation
from app.models.user import User
from app.models.workflow_execution import ExecutionStatus, WorkflowExecution
from app.platform.activity import ActivityService
from app.platform.events import DomainEventType, emit_event
from app.platform.search import SearchService
from app.platform.sre import ExplainabilityService, OperationsCenterService
from app.repositories.audit import AuditLogRepository
from app.models.control_plane import ClusterPolicyFinding
from app.repositories.control_plane import ControlPlaneOperationRepository
from app.repositories.delivery import (
    DeliveryDeploymentRepository,
    DeliveryOperationRepository,
    DeliveryPipelineRunRepository,
)
from app.repositories.incident import IncidentInvestigationRepository, MonitoringAlertRepository
from app.repositories.ops_workspace import (
    OpsAutomationRepository,
    OpsBriefingRepository,
    OpsCalendarRepository,
    OpsHandoverRepository,
    OpsMaintenanceRepository,
)
from app.schemas.devops_sre_workspace import MaintenanceCreate
from app.services.cost_optimization import CostOptimizationService
from app.services.delivery import DeliveryService
from app.services.document_export import render_pdf
from app.services.jobs import JobService
from app.services.reliability_dashboard import ReliabilityDashboardService
from app.services.service_health import ServiceHealthService
from app.tenancy.permissions import can_read_resources, can_write_resources
from app.workspace.types import (
    AutomationSuggestionKind,
    CalendarEventKind,
    MaintenanceKind,
    MaintenanceStatus,
    QueueItemType,
    QueuePriority,
)

logger = get_logger(__name__)

_PRIORITY_ORDER = {
    QueuePriority.CRITICAL.value: 0,
    QueuePriority.HIGH.value: 1,
    QueuePriority.MEDIUM.value: 2,
    QueuePriority.LOW.value: 3,
}
_SLA_MINUTES = {
    QueuePriority.CRITICAL.value: 60,
    QueuePriority.HIGH.value: 240,
    QueuePriority.MEDIUM.value: 1440,
    QueuePriority.LOW.value: 4320,
}


def _age_minutes(ts: datetime | None) -> int:
    if ts is None:
        return 0
    aware = ts if ts.tzinfo else ts.replace(tzinfo=UTC)
    return max(0, int((utcnow() - aware).total_seconds() / 60))


def _priority_rank(priority: str) -> int:
    return _PRIORITY_ORDER.get(priority, 99)


class DevOpsSREWorkspaceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.incidents = IncidentInvestigationRepository(session)
        self.alerts = MonitoringAlertRepository(session)
        self.dlv_deployments = DeliveryDeploymentRepository(session)
        self.dlv_operations = DeliveryOperationRepository(session)
        self.dlv_runs = DeliveryPipelineRunRepository(session)
        self.cp_operations = ControlPlaneOperationRepository(session)
        self.maintenance = OpsMaintenanceRepository(session)
        self.briefings = OpsBriefingRepository(session)
        self.handovers = OpsHandoverRepository(session)
        self.automation = OpsAutomationRepository(session)
        self.calendar = OpsCalendarRepository(session)
        self.audit = AuditLogRepository(session)
        self.ops_center = OperationsCenterService(session)
        self.delivery = DeliveryService(session)
        self.cost = CostOptimizationService(session)
        self.reliability = ReliabilityDashboardService(session)
        self.health = ServiceHealthService(session)
        self.jobs = JobService(session)
        self.activity = ActivityService(session)
        self.search = SearchService(session)
        self.explain = ExplainabilityService(session)

    def _ensure_read(self, user: User, org_context: OrgContext) -> str:
        if not can_read_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    def _ensure_write(self, user: User, org_context: OrgContext) -> str:
        if not can_write_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    async def _list_policy_findings(self, organization_id: str) -> list[ClusterPolicyFinding]:
        stmt = (
            select(ClusterPolicyFinding)
            .where(ClusterPolicyFinding.organization_id == organization_id)
            .order_by(ClusterPolicyFinding.created_at.desc())
            .limit(100)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def _slo_snapshot(self, user: User, org_context: OrgContext) -> dict:
        try:
            overview = await self.health.overview(user, org_context)
            return {
                "services_at_risk": overview.services_at_risk,
                "at_risk_services": [
                    {"name": s.name, "health_score": s.health_score, "burn_status": s.burn_status}
                    for s in overview.services if s.burn_status != "NORMAL" or s.health_score < 90
                ],
                "error_budget_remaining_percent": next(
                    (s.error_budget_remaining_percentage for s in overview.services
                     if s.error_budget_remaining_percentage is not None),
                    None,
                ),
            }
        except Exception:  # noqa: BLE001
            return {}

    # ------------------------------------------------------------------ queue
    async def _build_queue_items(self, organization_id: str) -> list[dict]:
        items: list[dict] = []

        inc_rows, _ = await self.incidents.list_for_org(organization_id, limit=50)
        for inc in inc_rows:
            lifecycle = getattr(inc, "lifecycle_status", None) or inc.status
            if lifecycle in ("RESOLVED", "CLOSED"):
                continue
            pri = QueuePriority.CRITICAL.value if inc.severity in ("CRITICAL", "SEV1") else QueuePriority.HIGH.value
            items.append({
                "id": f"incident-{inc.id}",
                "type": QueueItemType.INCIDENT.value,
                "title": inc.title,
                "owner": inc.created_by,
                "priority": pri,
                "status": lifecycle,
                "age_minutes": _age_minutes(inc.created_at),
                "sla_minutes": _SLA_MINUTES[pri],
                "suggested_action": "Investigate and mitigate",
                "reference_type": "incident",
                "reference_id": inc.id,
                "meta": {"severity": inc.severity},
            })

        alerts, _ = await self.alerts.list_for_org(organization_id, status="FIRING", limit=50)
        for alert in alerts:
            pri = QueuePriority.HIGH.value if alert.severity in ("CRITICAL", "HIGH") else QueuePriority.MEDIUM.value
            if alert.incident_id:
                suggested = "View incident — RCA & fixes ready"
                ref_type, ref_id = "incident", alert.incident_id
            else:
                suggested = "Investigate alert → create incident"
                ref_type, ref_id = "alert", alert.id
            items.append({
                "id": f"alert-{alert.id}",
                "type": QueueItemType.ALERT.value,
                "title": alert.alert_name or "Alert",
                "owner": None,
                "priority": pri,
                "status": alert.status,
                "age_minutes": _age_minutes(alert.last_seen_at or alert.created_at),
                "sla_minutes": _SLA_MINUTES[pri],
                "suggested_action": suggested,
                "reference_type": ref_type,
                "reference_id": ref_id,
                "meta": {
                    "severity": alert.severity,
                    "service": alert.service,
                    "incident_id": alert.incident_id,
                    "provider": alert.provider,
                },
            })

        for dep in await self.dlv_deployments.list_for_org(organization_id):
            if dep.status not in ("FAILED", "ROLLED_BACK"):
                continue
            items.append({
                "id": f"deployment-{dep.id}",
                "type": QueueItemType.DEPLOYMENT.value,
                "title": f"Failed deployment {dep.id[:8]}",
                "owner": None,
                "priority": QueuePriority.HIGH.value,
                "status": dep.status,
                "age_minutes": _age_minutes(dep.completed_at or dep.created_at),
                "sla_minutes": _SLA_MINUTES[QueuePriority.HIGH.value],
                "suggested_action": "Review logs and rollback or redeploy",
                "reference_type": "deployment",
                "reference_id": dep.id,
                "meta": {"error": dep.error},
            })

        for op in await self.dlv_operations.list_for_org(organization_id):
            if op.status == DeliveryStatus.PENDING_APPROVAL.value:
                items.append({
                    "id": f"approval-dlv-{op.id}",
                    "type": QueueItemType.APPROVAL.value,
                    "title": f"Approve {op.kind} operation",
                    "owner": op.requested_by,
                    "priority": QueuePriority.HIGH.value,
                    "status": op.status,
                    "age_minutes": _age_minutes(op.created_at),
                    "sla_minutes": _SLA_MINUTES[QueuePriority.HIGH.value],
                    "suggested_action": "Review and approve or reject",
                    "reference_type": "delivery_operation",
                    "reference_id": op.id,
                    "meta": {"kind": op.kind},
                })

        for op in await self.cp_operations.list_for_org(organization_id):
            if op.status == "PENDING_APPROVAL":
                items.append({
                    "id": f"approval-cp-{op.id}",
                    "type": QueueItemType.APPROVAL.value,
                    "title": f"Approve {op.kind} on cluster",
                    "owner": op.requested_by,
                    "priority": QueuePriority.HIGH.value,
                    "status": op.status,
                    "age_minutes": _age_minutes(op.created_at),
                    "sla_minutes": _SLA_MINUTES[QueuePriority.HIGH.value],
                    "suggested_action": "Review control plane operation",
                    "reference_type": "control_plane_operation",
                    "reference_id": op.id,
                    "meta": {"kind": op.kind, "cluster_id": op.cluster_id},
                })

        commander = await self.ops_center.commander.list_active(organization_id=organization_id)
        for run in commander:
            items.append({
                "id": f"investigation-{run.id}",
                "type": QueueItemType.INVESTIGATION.value,
                "title": f"AI investigation for incident {run.incident_id[:8]}",
                "owner": None,
                "priority": QueuePriority.MEDIUM.value,
                "status": run.status,
                "age_minutes": _age_minutes(run.created_at),
                "sla_minutes": _SLA_MINUTES[QueuePriority.MEDIUM.value],
                "suggested_action": "Review AI findings and take action",
                "reference_type": "investigation",
                "reference_id": run.id,
                "meta": {"incident_id": run.incident_id},
            })

        for job in await self.jobs.list(organization_id, status=JobStatus.DEAD_LETTER.value, limit=20):
            items.append({
                "id": f"job-{job.id}",
                "type": QueueItemType.FAILED_JOB.value,
                "title": f"Failed job: {job.job_type}",
                "owner": None,
                "priority": QueuePriority.MEDIUM.value,
                "status": job.status,
                "age_minutes": _age_minutes(job.updated_at or job.created_at),
                "sla_minutes": _SLA_MINUTES[QueuePriority.MEDIUM.value],
                "suggested_action": "Retry or investigate job failure",
                "reference_type": "job",
                "reference_id": job.id,
                "meta": {"error": job.error},
            })

        wf_stmt = (
            select(WorkflowExecution)
            .where(
                WorkflowExecution.organization_id == organization_id,
                WorkflowExecution.status == ExecutionStatus.FAILED,
            )
            .order_by(WorkflowExecution.updated_at.desc())
            .limit(20)
        )
        for wf in (await self.session.execute(wf_stmt)).scalars().all():
            items.append({
                "id": f"workflow-{wf.id}",
                "type": QueueItemType.FAILED_WORKFLOW.value,
                "title": f"Failed workflow execution",
                "owner": None,
                "priority": QueuePriority.MEDIUM.value,
                "status": wf.status.value,
                "age_minutes": _age_minutes(wf.updated_at or wf.created_at),
                "sla_minutes": _SLA_MINUTES[QueuePriority.MEDIUM.value],
                "suggested_action": "Review workflow execution logs",
                "reference_type": "workflow_execution",
                "reference_id": wf.id,
                "meta": {},
            })

        for run in await self.dlv_runs.list_for_org(organization_id, limit=30):
            if run.status != "FAILED":
                continue
            items.append({
                "id": f"pipeline-{run.id}",
                "type": QueueItemType.FAILED_WORKFLOW.value,
                "title": f"Failed pipeline run {run.external_id or run.id[:8]}",
                "owner": None,
                "priority": QueuePriority.MEDIUM.value,
                "status": run.status,
                "age_minutes": _age_minutes(run.finished_at or run.created_at),
                "sla_minutes": _SLA_MINUTES[QueuePriority.MEDIUM.value],
                "suggested_action": "Inspect pipeline logs and fix",
                "reference_type": "pipeline_run",
                "reference_id": run.id,
                "meta": {"pipeline_id": run.pipeline_id},
            })

        for finding in await self._list_policy_findings(organization_id):
            if finding.acknowledged:
                continue
            kind = QueueItemType.DRIFT.value if "drift" in finding.policy.lower() else QueueItemType.COMPLIANCE.value
            pri = QueuePriority.HIGH.value if finding.severity in ("CRITICAL", "HIGH") else QueuePriority.MEDIUM.value
            items.append({
                "id": f"finding-{finding.id}",
                "type": kind,
                "title": finding.message[:120],
                "owner": None,
                "priority": pri,
                "status": "OPEN",
                "age_minutes": _age_minutes(finding.created_at),
                "sla_minutes": _SLA_MINUTES[pri],
                "suggested_action": finding.recommendation[:200],
                "reference_type": "policy_finding",
                "reference_id": finding.id,
                "meta": {"policy": finding.policy, "cluster_id": finding.cluster_id},
            })

        recs = list((await self.session.execute(
            select(SREAIRecommendation).where(
                SREAIRecommendation.organization_id == organization_id,
            ).order_by(SREAIRecommendation.created_at.desc()).limit(10)
        )).scalars().all())
        for rec in recs:
            items.append({
                "id": f"ai-rec-{rec.id}",
                "type": QueueItemType.AI_RECOMMENDATION.value,
                "title": rec.title,
                "owner": None,
                "priority": QueuePriority.LOW.value,
                "status": "ACTIVE",
                "age_minutes": _age_minutes(rec.created_at),
                "sla_minutes": _SLA_MINUTES[QueuePriority.LOW.value],
                "suggested_action": "Review AI recommendation",
                "reference_type": "ai_recommendation",
                "reference_id": rec.id,
                "meta": self.explain.bundle(rec),
            })

        items.sort(key=lambda i: (_priority_rank(i["priority"]), -i["age_minutes"]))
        return items

    # ----------------------------------------------------------- my work dash
    async def my_work(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        queue = await self._build_queue_items(organization_id)
        ops_dash = await self.ops_center.dashboard(
            organization_id=organization_id, user=user, org_context=org_context,
        )
        dlv_dash = await self.delivery.dashboard(user, org_context)
        cost_dash = await self.cost.dashboard(user, org_context)
        findings = await self._list_policy_findings(organization_id)
        cert_findings = [f for f in findings if "cert" in f.policy.lower() or "tls" in f.policy.lower()]
        cred_findings = [f for f in findings if "secret" in f.policy.lower() or "credential" in f.policy.lower()]
        maintenance_rows = await self.maintenance.list_for_org(organization_id)
        upcoming_maint = [m for m in maintenance_rows if m.status == MaintenanceStatus.SCHEDULED.value]

        slo_data = await self._slo_snapshot(user, org_context)

        sections = [
            {"key": "incidents", "label": "Active Incidents", "count": len(ops_dash["active_incidents"]),
             "priority": QueuePriority.CRITICAL.value, "items": ops_dash["active_incidents"][:5]},
            {"key": "alerts", "label": "Open Alerts", "count": sum(1 for q in queue if q["type"] == "ALERT"),
             "priority": QueuePriority.HIGH.value,
             "items": [q for q in queue if q["type"] == "ALERT"][:5]},
            {"key": "failed_deployments", "label": "Failed Deployments",
             "count": sum(1 for q in queue if q["type"] == "DEPLOYMENT"),
             "priority": QueuePriority.HIGH.value,
             "items": [q for q in queue if q["type"] == "DEPLOYMENT"][:5]},
            {"key": "pending_approvals", "label": "Pending Approvals",
             "count": dlv_dash["pending_operations"] + sum(1 for q in queue if q["type"] == "APPROVAL"),
             "priority": QueuePriority.HIGH.value,
             "items": [q for q in queue if q["type"] == "APPROVAL"][:5]},
            {"key": "investigations", "label": "Assigned Investigations",
             "count": len(ops_dash["ai_investigations"]),
             "priority": QueuePriority.MEDIUM.value, "items": ops_dash["ai_investigations"][:5]},
            {"key": "ai_recommendations", "label": "AI Recommendations",
             "count": len(ops_dash["ai_recommendations"]),
             "priority": QueuePriority.LOW.value, "items": ops_dash["ai_recommendations"][:5]},
            {"key": "slo_violations", "label": "SLO Violations",
             "count": slo_data.get("services_at_risk", 0) if slo_data else 0,
             "priority": QueuePriority.HIGH.value,
             "items": slo_data.get("at_risk_services", [])[:5] if slo_data else []},
            {"key": "error_budget", "label": "Error Budget Status",
             "count": 1 if slo_data.get("error_budget_remaining_percent") is not None else 0,
             "priority": QueuePriority.MEDIUM.value,
             "items": [{"remaining_percent": slo_data.get("error_budget_remaining_percent")}] if slo_data else []},
            {"key": "cost_anomalies", "label": "Cost Anomalies",
             "count": 1 if cost_dash.has_data and (cost_dash.estimated_waste or 0) > 0 else 0,
             "priority": QueuePriority.MEDIUM.value,
             "items": [{"waste": cost_dash.estimated_waste, "savings": cost_dash.potential_savings}] if cost_dash.has_data else []},
            {"key": "certificates", "label": "Expiring Certificates", "count": len(cert_findings),
             "priority": QueuePriority.HIGH.value,
             "items": [{"message": f.message, "cluster_id": f.cluster_id} for f in cert_findings[:5]]},
            {"key": "credentials", "label": "Expiring Credentials", "count": len(cred_findings),
             "priority": QueuePriority.MEDIUM.value,
             "items": [{"message": f.message} for f in cred_findings[:5]]},
            {"key": "maintenance", "label": "Scheduled Maintenance", "count": len(upcoming_maint),
             "priority": QueuePriority.LOW.value,
             "items": [{"id": m.id, "title": m.title, "starts_at": str(m.starts_at)} for m in upcoming_maint[:5]]},
            {"key": "cluster_changes", "label": "Recent Cluster Changes",
             "count": len(await self.cp_operations.list_for_org(organization_id)),
             "priority": QueuePriority.MEDIUM.value, "items": []},
        ]
        sections = [s for s in sections if s["count"] > 0]
        sections.sort(key=lambda s: _priority_rank(s["priority"]))
        total = sum(s["count"] for s in sections)
        await self.audit.log(
            action="ops_workspace.my_work_viewed",
            resource_type="ops_workspace",
            resource_id=organization_id,
            user_id=user.id,
        )
        return {"sections": sections, "total_attention_items": total, "updated_at": utcnow()}

    async def queue(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        items = await self._build_queue_items(organization_id)
        await self.audit.log(
            action="ops_workspace.queue_viewed",
            resource_type="ops_workspace",
            resource_id=organization_id,
            user_id=user.id,
        )
        return {"items": items, "total": len(items)}

    # ------------------------------------------------------------- change ctr
    async def changes(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        events: list[dict] = []

        for dep in await self.dlv_deployments.list_for_org(organization_id):
            events.append({
                "id": f"dlv-dep-{dep.id}",
                "kind": "DEPLOYMENT",
                "title": f"Deployment {dep.status}",
                "actor": None,
                "status": dep.status,
                "occurred_at": dep.completed_at or dep.created_at,
                "reference_type": "deployment",
                "reference_id": dep.id,
                "meta": {"strategy": dep.strategy, "environment_id": dep.environment_id},
            })

        for op in await self.cp_operations.list_for_org(organization_id):
            events.append({
                "id": f"cp-op-{op.id}",
                "kind": "INFRASTRUCTURE",
                "title": f"{op.kind} — {op.status}",
                "actor": op.requested_by,
                "status": op.status,
                "occurred_at": op.executed_at or op.created_at,
                "reference_type": "control_plane_operation",
                "reference_id": op.id,
                "meta": {"cluster_id": op.cluster_id},
            })

        for op in await self.dlv_operations.list_for_org(organization_id):
            events.append({
                "id": f"dlv-op-{op.id}",
                "kind": "MANUAL_OPERATION" if op.kind != "DEPLOY" else "DEPLOYMENT",
                "title": f"{op.kind} — {op.status}",
                "actor": op.requested_by,
                "status": op.status,
                "occurred_at": op.executed_at or op.created_at,
                "reference_type": "delivery_operation",
                "reference_id": op.id,
                "meta": {},
            })

        for finding in await self._list_policy_findings(organization_id):
            if not finding.acknowledged:
                events.append({
                    "id": f"drift-{finding.id}",
                    "kind": "DRIFT",
                    "title": finding.message[:100],
                    "actor": None,
                    "status": "OPEN",
                    "occurred_at": finding.created_at,
                    "reference_type": "policy_finding",
                    "reference_id": finding.id,
                    "meta": {"policy": finding.policy},
                })

        events.sort(key=lambda e: e["occurred_at"], reverse=True)
        return {"events": events[:200], "total": len(events)}

    # ---------------------------------------------------------- maintenance
    async def list_maintenance(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        rows = await self.maintenance.list_for_org(organization_id)
        now = utcnow()
        upcoming = [r for r in rows if r.starts_at > now and r.status == MaintenanceStatus.SCHEDULED.value]
        active_freezes = [
            r for r in rows
            if r.kind == MaintenanceKind.FREEZE.value and r.status == MaintenanceStatus.ACTIVE.value
        ]
        return {"windows": rows, "upcoming": upcoming, "active_freezes": active_freezes}

    async def create_maintenance(
        self, user: User, org_context: OrgContext, payload: MaintenanceCreate,
    ) -> WorkspaceMaintenanceWindow:
        organization_id = self._ensure_write(user, org_context)
        row = WorkspaceMaintenanceWindow(
            organization_id=organization_id,
            kind=payload.kind,
            title=payload.title,
            description=payload.description,
            status=MaintenanceStatus.SCHEDULED.value,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            impact_summary=payload.impact_summary,
            cluster_id=payload.cluster_id,
            environment_id=payload.environment_id,
            requires_approval=payload.requires_approval,
            created_by=user.id,
        )
        self.session.add(row)
        await self.session.flush()
        self.session.add(WorkspaceCalendarEvent(
            organization_id=organization_id,
            kind=CalendarEventKind.MAINTENANCE.value,
            title=payload.title,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            reference_type="maintenance_window",
            reference_id=row.id,
            meta={"kind": payload.kind},
        ))
        await emit_event(
            self.session,
            event_type=DomainEventType.OPS_MAINTENANCE_SCHEDULED,
            organization_id=organization_id,
            actor_id=user.id,
            aggregate_type="maintenance_window",
            aggregate_id=row.id,
            payload={"title": payload.title, "kind": payload.kind},
        )
        await self.audit.log(
            action="ops_workspace.maintenance_created",
            resource_type="maintenance_window",
            resource_id=row.id,
            user_id=user.id,
        )
        return row

    async def approve_maintenance(
        self, user: User, org_context: OrgContext, window_id: str, *, approved: bool,
    ) -> WorkspaceMaintenanceWindow:
        organization_id = self._ensure_write(user, org_context)
        row = await self.maintenance.get_by_id(window_id)
        if not row or row.organization_id != organization_id:
            raise NotFoundError("MaintenanceWindow", window_id)
        if approved:
            row.approved_by = user.id
            row.status = MaintenanceStatus.SCHEDULED.value
        else:
            row.status = MaintenanceStatus.CANCELLED.value
        await self.session.flush()
        await self.audit.log(
            action="ops_workspace.maintenance_decided",
            resource_type="maintenance_window",
            resource_id=window_id,
            user_id=user.id,
            details={"approved": approved},
        )
        return row

    # -------------------------------------------------------------- calendar
    async def calendar_events(self, user: User, org_context: OrgContext) -> list[WorkspaceCalendarEvent]:
        organization_id = self._ensure_read(user, org_context)
        stored = await self.calendar.list_for_org(organization_id)
        if stored:
            return stored
        # Seed from maintenance windows when calendar is empty.
        for mw in await self.maintenance.list_for_org(organization_id):
            self.session.add(WorkspaceCalendarEvent(
                organization_id=organization_id,
                kind=CalendarEventKind.MAINTENANCE.value,
                title=mw.title,
                starts_at=mw.starts_at,
                ends_at=mw.ends_at,
                reference_type="maintenance_window",
                reference_id=mw.id,
            ))
        await self.session.flush()
        return await self.calendar.list_for_org(organization_id)

    # ------------------------------------------------------------------ slo
    async def slo_center(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        dash = await self.reliability.dashboard(
            user, org_context, scope="organization", scope_value=organization_id, window_days=30,
        )
        try:
            overview = await self.health.overview(user, org_context)
            health = {
                "slis": [{"service": s.name, "availability_30d": s.availability_30d} for s in overview.services],
                "slos": [{"service": s.name, "burn_status": s.burn_status} for s in overview.services],
                "error_budgets": [
                    {"service": s.name, "remaining_percent": s.error_budget_remaining_percentage}
                    for s in overview.services if s.error_budget_remaining_percentage is not None
                ],
                "burn_rates": [
                    {"service": s.name, "burn_rate": s.burn_rate, "status": s.burn_status}
                    for s in overview.services
                ],
            }
        except Exception:  # noqa: BLE001
            health = {"slis": [], "slos": [], "error_budgets": [], "burn_rates": []}
        ops_dash = await self.ops_center.dashboard(organization_id=organization_id)
        return {
            "slis": health.get("slis", []),
            "slos": health.get("slos", []),
            "error_budgets": health.get("error_budgets", []),
            "burn_rates": health.get("burn_rates", []),
            "predictions": ops_dash.get("predictions", []),
            "ai_recommendations": ops_dash.get("ai_recommendations", []),
            "linked_incidents": ops_dash.get("active_incidents", []),
            "linked_deployments": [],
            "reliability_score": dash.reliability_score if hasattr(dash, "reliability_score") else None,
            "metrics": dash.metrics.model_dump() if hasattr(dash, "metrics") else {},
        }

    # ------------------------------------------------------------------ cost
    async def cost_operations(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        dash = await self.cost.dashboard(user, org_context)
        daily = (dash.current_cost / 30.0) if dash.has_data and dash.current_cost else None
        return {
            "has_data": dash.has_data,
            "daily_spend": round(daily, 2) if daily else None,
            "namespace_spend": dash.cost_by_environment or [],
            "cluster_spend": dash.cost_by_service or [],
            "idle_resources": dash.idle_count,
            "waste_estimate": dash.estimated_waste,
            "rightsizing": [
                r.model_dump() if hasattr(r, "model_dump") else r
                for r in (dash.top_recommendations or [])
                if (r.kind if hasattr(r, "kind") else r.get("kind")) == "RIGHTSIZING"
            ],
            "recommendations": [
                r.model_dump() if hasattr(r, "model_dump") else r
                for r in (dash.top_recommendations or [])
            ],
            "projected_monthly_bill": dash.forecast_30d,
        }

    # ------------------------------------------------------------- executive
    async def executive(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        dash = await self.reliability.dashboard(
            user, org_context, scope="organization", scope_value=organization_id, window_days=30,
        )
        dora = await self.delivery.dora_metrics(user, org_context)
        m = dash.metrics
        inc_rows, _ = await self.incidents.list_for_org(organization_id, limit=5)
        return {
            "platform_health_score": dash.reliability_score,
            "deployment_success_rate": m.deployment_success_rate,
            "availability": m.availability_30d,
            "mttr_hours": (m.mttr_minutes / 60.0) if m.mttr_minutes else None,
            "mttd_hours": (m.mtta_minutes / 60.0) if m.mtta_minutes else None,
            "dora": dora.__dict__,
            "top_incidents": [{"id": i.id, "title": i.title, "status": i.status} for i in inc_rows],
            "top_risks": [r.model_dump() for r in (m.highest_risk_services or [])],
            "monthly_trend": [b.model_dump() for b in dash.trends_30d.buckets] if dash.trends_30d else [],
            "business_impact": (
                f"{m.open_incidents} open incidents; "
                f"{m.services_at_risk} services at risk"
            ),
        }

    async def executive_pdf(self, user: User, org_context: OrgContext) -> bytes:
        data = await self.executive(user, org_context)
        md = (
            f"# Executive Operations View\n\n"
            f"**Platform Health:** {data.get('platform_health_score', '—')}\n\n"
            f"**Availability (30d):** {data.get('availability', '—')}%\n\n"
            f"**MTTR:** {data.get('mttr_hours', '—')}h\n\n"
            f"**Deployment Success:** {data.get('deployment_success_rate', '—')}%\n\n"
        )
        for inc in data.get("top_incidents", [])[:5]:
            md += f"- Incident: {inc['title']} ({inc['status']})\n"
        return render_pdf(md)

    # -------------------------------------------------------- daily briefing
    async def generate_daily_briefing(self, user: User, org_context: OrgContext) -> WorkspaceDailyBriefing:
        organization_id = self._ensure_write(user, org_context)
        my_work = await self.my_work(user, org_context)
        queue_data = await self.queue(user, org_context)
        cost = await self.cost_operations(user, org_context)
        today = utcnow().strftime("%Y-%m-%d")
        sections = {
            "platform_summary": f"{my_work['total_attention_items']} items need attention",
            "incidents_overnight": [s for s in my_work["sections"] if s["key"] == "incidents"],
            "failed_deployments": [s for s in my_work["sections"] if s["key"] == "failed_deployments"],
            "cost_spikes": {"waste": cost.get("waste_estimate")} if cost.get("waste_estimate") else {},
            "pending_approvals": [s for s in my_work["sections"] if s["key"] == "pending_approvals"],
            "queue_top": queue_data["items"][:10],
        }
        actions = [
            q["suggested_action"] for q in queue_data["items"][:5]
        ]
        summary = (
            f"Daily briefing for {today}: {my_work['total_attention_items']} attention items. "
            f"Top priority: {queue_data['items'][0]['title'] if queue_data['items'] else 'All clear'}."
        )
        row = WorkspaceDailyBriefing(
            organization_id=organization_id,
            briefing_date=today,
            summary=summary,
            sections=sections,
            recommended_actions=actions,
            generated_by=user.id,
        )
        self.session.add(row)
        await self.session.flush()
        await self.activity.record(
            event_type=DomainEventType.OPS_DAILY_BRIEFING.value,
            organization_id=organization_id,
            actor_id=user.id,
            verb="generated the daily operations briefing",
            object_type="daily_briefing",
            object_id=row.id,
            summary=summary,
            meta=sections,
        )
        await emit_event(
            self.session,
            event_type=DomainEventType.OPS_DAILY_BRIEFING,
            organization_id=organization_id,
            actor_id=user.id,
            aggregate_type="daily_briefing",
            aggregate_id=row.id,
            payload={"summary": summary},
        )
        await self.audit.log(
            action="ops_workspace.briefing_generated",
            resource_type="daily_briefing",
            resource_id=row.id,
            user_id=user.id,
        )
        return row

    async def latest_briefing(self, user: User, org_context: OrgContext) -> WorkspaceDailyBriefing | None:
        organization_id = self._ensure_read(user, org_context)
        return await self.briefings.latest(organization_id)

    # ----------------------------------------------------------- shift handover
    async def generate_handover(self, user: User, org_context: OrgContext) -> WorkspaceShiftHandover:
        organization_id = self._ensure_write(user, org_context)
        queue_data = await self.queue(user, org_context)
        maint = await self.list_maintenance(user, org_context)
        exec_view = await self.executive(user, org_context)
        sections = {
            "platform_state": exec_view,
            "open_incidents": [q for q in queue_data["items"] if q["type"] == "INCIDENT"],
            "investigations": [q for q in queue_data["items"] if q["type"] == "INVESTIGATION"],
            "pending_work": queue_data["items"][:15],
            "blocked_deployments": [q for q in queue_data["items"] if q["type"] == "DEPLOYMENT"],
            "upcoming_maintenance": maint["upcoming"][:5],
            "recommendations": exec_view.get("top_risks", []),
        }
        md = f"# Shift Handover — {utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        md += f"## Platform State\nHealth score: {exec_view.get('platform_health_score', '—')}\n\n"
        md += f"## Open Incidents ({len(sections['open_incidents'])})\n"
        for item in sections["open_incidents"][:10]:
            md += f"- {item['title']} ({item['status']})\n"
        md += f"\n## Pending Work ({len(sections['pending_work'])})\n"
        for item in sections["pending_work"][:10]:
            md += f"- [{item['priority']}] {item['title']}: {item['suggested_action']}\n"
        row = WorkspaceShiftHandover(
            organization_id=organization_id,
            title=f"Shift handover {utcnow().strftime('%Y-%m-%d %H:%M')}",
            markdown=md,
            sections=sections,
            generated_by=user.id,
        )
        self.session.add(row)
        await self.session.flush()
        await emit_event(
            self.session,
            event_type=DomainEventType.OPS_SHIFT_HANDOVER,
            organization_id=organization_id,
            actor_id=user.id,
            aggregate_type="shift_handover",
            aggregate_id=row.id,
            payload={"title": row.title},
        )
        await self.audit.log(
            action="ops_workspace.handover_generated",
            resource_type="shift_handover",
            resource_id=row.id,
            user_id=user.id,
        )
        return row

    async def handover_pdf(self, user: User, org_context: OrgContext, handover_id: str | None = None) -> bytes:
        organization_id = self._ensure_read(user, org_context)
        if handover_id:
            row = await self.handovers.get_by_id(handover_id)
        else:
            row = await self.handovers.latest(organization_id)
        if not row or row.organization_id != organization_id:
            raise NotFoundError("ShiftHandover", handover_id or "latest")
        return render_pdf(row.markdown)

    async def latest_handover(self, user: User, org_context: OrgContext) -> WorkspaceShiftHandover | None:
        organization_id = self._ensure_read(user, org_context)
        return await self.handovers.latest(organization_id)

    # -------------------------------------------------------------- search
    async def unified_search(
        self, user: User, org_context: OrgContext, *, query: str, limit: int = 20,
    ) -> dict:
        organization_id = self._ensure_read(user, org_context)
        return await self.search.search(
            query, organization_id=organization_id, limit=limit, user_id=user.id,
        )

    # ------------------------------------------------------------------ kpis
    async def kpis(self, user: User, org_context: OrgContext, *, window_days: int = 30) -> dict:
        organization_id = self._ensure_read(user, org_context)
        dash = await self.reliability.dashboard(
            user, org_context, scope="organization", scope_value=organization_id, window_days=window_days,
        )
        dora = await self.delivery.dora_metrics(user, org_context, window_days=window_days)
        m = dash.metrics
        failed_jobs = await self.jobs.count(organization_id, status=JobStatus.DEAD_LETTER.value)
        total_jobs = await self.jobs.count(organization_id)
        automation_rate = (
            round(100.0 * (1 - failed_jobs / max(total_jobs, 1)), 1) if total_jobs else None
        )
        return {
            "mttr_hours": (m.mttr_minutes / 60.0) if m.mttr_minutes else dora.mttr_hours,
            "mttd_hours": (m.mtta_minutes / 60.0) if m.mtta_minutes else None,
            "mtta_hours": (m.mtta_minutes / 60.0) if m.mtta_minutes else None,
            "availability_percent": m.availability_30d,
            "deployment_frequency_per_day": dora.deployment_frequency_per_day,
            "lead_time_hours": dora.lead_time_hours,
            "change_failure_rate_percent": dora.change_failure_rate_percent,
            "error_budget_burn_rate": None,
            "incident_recurrence_rate": None,
            "automation_success_rate": automation_rate,
            "approval_time_hours": None,
            "ai_recommendation_acceptance_rate": None,
            "window_days": window_days,
        }

    # ------------------------------------------------ automation suggestions
    async def automation_suggestions(self, user: User, org_context: OrgContext) -> list[WorkspaceAutomationSuggestion]:
        organization_id = self._ensure_read(user, org_context)
        existing = await self.automation.list_active(organization_id)
        if existing:
            return existing

        suggestions: list[WorkspaceAutomationSuggestion] = []
        deploy_failures = [
            d for d in await self.dlv_deployments.list_for_org(organization_id) if d.status == "FAILED"
        ]
        if len(deploy_failures) >= 3:
            env_counts: dict[str, int] = {}
            for d in deploy_failures:
                key = d.environment_id or "unknown"
                env_counts[key] = env_counts.get(key, 0) + 1
            top_env = max(env_counts, key=env_counts.get)
            suggestions.append(WorkspaceAutomationSuggestion(
                organization_id=organization_id,
                kind=AutomationSuggestionKind.WORKFLOW.value,
                title="Repeated deployment failures detected",
                pattern=f"Environment {top_env} has {env_counts[top_env]} failed deployments",
                occurrence_count=env_counts[top_env],
                recommendation="Create an automated rollback workflow or pre-deploy validation policy",
                evidence={"environment_id": top_env, "failures": env_counts[top_env]},
            ))

        approvals = await self.dlv_operations.list_for_org(organization_id)
        approved_ops = [o for o in approvals if o.status == DeliveryStatus.SUCCEEDED.value]
        if len(approved_ops) >= 5:
            kinds: dict[str, int] = {}
            for o in approved_ops:
                kinds[o.kind] = kinds.get(o.kind, 0) + 1
            for kind, count in kinds.items():
                if count >= 5:
                    suggestions.append(WorkspaceAutomationSuggestion(
                        organization_id=organization_id,
                        kind=AutomationSuggestionKind.POLICY.value,
                        title=f"Repetitive {kind} approvals",
                        pattern=f"{kind} approved {count} times with similar parameters",
                        occurrence_count=count,
                        recommendation=f"Auto-approve {kind} for non-production environments",
                        evidence={"kind": kind, "count": count},
                    ))

        for s in suggestions:
            self.session.add(s)
        await self.session.flush()
        return suggestions or existing

    async def dismiss_automation(
        self, user: User, org_context: OrgContext, suggestion_id: str,
    ) -> WorkspaceAutomationSuggestion:
        organization_id = self._ensure_write(user, org_context)
        row = await self.automation.get_by_id(suggestion_id)
        if not row or row.organization_id != organization_id:
            raise NotFoundError("AutomationSuggestion", suggestion_id)
        row.dismissed = True
        await self.session.flush()
        return row

    # ----------------------------------------------------------- AI context
    async def ai_context(
        self,
        user: User,
        org_context: OrgContext,
        *,
        page: str | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
        question: str | None = None,
    ) -> dict:
        organization_id = self._ensure_read(user, org_context)
        context: dict = {
            "page": page,
            "reference_type": reference_type,
            "reference_id": reference_id,
            "organization_id": organization_id,
        }
        if reference_type == "incident" and reference_id:
            inc = await self.incidents.get_for_org(reference_id, organization_id)
            if inc:
                context["incident"] = {"id": inc.id, "title": inc.title, "status": inc.status}
        elif reference_type == "deployment" and reference_id:
            for d in await self.dlv_deployments.list_for_org(organization_id):
                if d.id == reference_id:
                    context["deployment"] = {
                        "id": d.id, "status": d.status, "error": d.error, "strategy": d.strategy,
                    }
                    break
        elif reference_type == "alert" and reference_id:
            alert = await self.alerts.get_for_org(reference_id, organization_id)
            if alert:
                context["alert"] = {
                    "id": alert.id, "title": alert.alert_name, "severity": alert.severity,
                    "status": alert.status,
                }
        else:
            queue = await self._build_queue_items(organization_id)
            context["queue_summary"] = queue[:5]

        questions = [
            "Why is this deployment unhealthy?",
            "Explain this alert.",
            "Summarize this incident.",
            "Recommend remediation.",
            "Estimate blast radius.",
        ]
        if page == "slo":
            questions = ["Which SLO is at risk?", "What is the error budget burn rate?"]
        elif page == "cost":
            questions = ["Where is the biggest waste?", "What rightsizing do you recommend?"]

        await self.audit.log(
            action="ops_workspace.ai_context_viewed",
            resource_type="ops_workspace",
            resource_id=organization_id,
            user_id=user.id,
            details={"page": page, "question": question},
        )
        return {
            "context": context,
            "suggested_questions": questions,
            "copilot_endpoint": "/v1/copilot/chat",
        }
