"""Sprint 42C — Service Health & SLO Intelligence engine.

Strictly read-only analytics. Computes, from existing data (monitoring alerts,
incidents, on-call assignments, deployments):

* availability % over 24h / 7d / 30d (from merged incident-downtime intervals)
* error budget (allowed vs consumed vs remaining) for the availability SLO
* burn rate (recent 24h unavailability ÷ allowed unavailability) + status
* SLO violation prediction (days to error-budget exhaustion)
* per-SLO compliance (availability / error-rate / latency)
* incident/alert/deployment correlation ("what impacted this SLO?")
* a composite health score, plus per-service MTTA/MTTR

Formulas
--------
window_minutes        = window_days * 24 * 60
allowed_downtime      = window_minutes * (1 - target/100)
availability%(w)      = (w_minutes - downtime_in_w) / w_minutes * 100
burn_rate             = (downtime_24h / 1440) / (1 - target/100)
days_to_exhaustion    = remaining_minutes / downtime_24h
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NexoraException
from app.models.deployment import DeploymentRun
from app.models.incident import IncidentInvestigationStatus, MonitoringAlertStatus
from app.models.slo import SLOType
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.incident import (
    IncidentInvestigationRepository,
    MonitoringAlertRepository,
)
from app.repositories.oncall import IncidentAssignmentRepository
from app.repositories.slo import ServiceRepository, ServiceSLORepository
from app.schemas.slo import (
    AvailabilityWindow,
    BurnRate,
    CorrelatedAlert,
    CorrelatedDeployment,
    CorrelatedIncident,
    ErrorBudget,
    ServiceHealthOverview,
    ServiceHealthReport,
    ServiceHealthSummary,
    SLOComplianceItem,
    SLOPrediction,
)
from app.tenancy.permissions import can_read_ai_teams, can_write_ai_teams

logger = structlog.get_logger(__name__)

_LATENCY_HINTS = ("laten", "p50", "p95", "p99", "response_time", "responsetime")


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _merge_minutes(intervals: list[tuple[datetime, datetime]]) -> float:
    """Total minutes covered by a set of (start, end) intervals, merging overlaps."""
    spans = sorted((s, e) for s, e in intervals if e > s)
    if not spans:
        return 0.0
    total = 0.0
    cur_s, cur_e = spans[0]
    for s, e in spans[1:]:
        if s <= cur_e:
            cur_e = max(cur_e, e)
        else:
            total += (cur_e - cur_s).total_seconds()
            cur_s, cur_e = s, e
    total += (cur_e - cur_s).total_seconds()
    return total / 60.0


def _round(v: float | None, n: int = 2) -> float | None:
    return round(v, n) if v is not None else None


class ServiceHealthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.service_repo = ServiceRepository(session)
        self.slo_repo = ServiceSLORepository(session)
        self.alert_repo = MonitoringAlertRepository(session)
        self.incident_repo = IncidentInvestigationRepository(session)
        self.assignment_repo = IncidentAssignmentRepository(session)
        self.audit_repo = AuditLogRepository(session)

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

    # ---------------------------------------------------------------- catalog
    async def create_service(self, user, org_context, data):
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        service = await self.service_repo.create(
            organization_id=organization_id,
            name=data.name,
            description=data.description,
            owner_team=data.owner_team,
            tier=(data.tier or "TIER_2").upper(),
        )
        await self.audit_repo.log(
            action="service_created",
            resource_type="service",
            resource_id=service.id,
            user_id=user.id,
            details={"organization_id": organization_id, "name": data.name},
        )
        await self.session.commit()
        return service

    async def list_services(self, user, org_context):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        return await self.service_repo.list_for_org(organization_id)

    async def get_service(self, user, org_context, service_id):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        return await self.service_repo.get_for_org(service_id, organization_id)

    async def update_service(self, user, org_context, service_id, data):
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        service = await self.service_repo.get_for_org(service_id, organization_id)
        if service is None:
            raise NexoraException("Service not found.", status_code=404)
        if data.description is not None:
            service.description = data.description
        if data.owner_team is not None:
            service.owner_team = data.owner_team
        if data.tier is not None:
            service.tier = data.tier.upper()
        await self.audit_repo.log(
            action="service_updated",
            resource_type="service",
            resource_id=service.id,
            user_id=user.id,
            details={"organization_id": organization_id},
        )
        await self.session.commit()
        return service

    async def delete_service(self, user, org_context, service_id):
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        service = await self.service_repo.get_for_org(service_id, organization_id)
        if service is None:
            raise NexoraException("Service not found.", status_code=404)
        await self.session.delete(service)
        await self.audit_repo.log(
            action="service_deleted",
            resource_type="service",
            resource_id=service_id,
            user_id=user.id,
            details={"organization_id": organization_id},
        )
        await self.session.commit()

    # ------------------------------------------------------------------ slos
    async def create_slo(self, user, org_context, service_id, data):
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        service = await self.service_repo.get_for_org(service_id, organization_id)
        if service is None:
            raise NexoraException("Service not found.", status_code=404)
        slo_type = (data.slo_type or "AVAILABILITY").upper()
        if slo_type not in {t.value for t in SLOType}:
            raise NexoraException("Invalid slo_type.", status_code=400)
        slo = await self.slo_repo.create(
            organization_id=organization_id,
            service_id=service_id,
            name=data.name,
            slo_type=slo_type,
            target_percentage=data.target_percentage,
            window_days=data.window_days,
            latency_percentile=(data.latency_percentile.upper() if data.latency_percentile else None),
            threshold_ms=data.threshold_ms,
        )
        await self.audit_repo.log(
            action="service_slo_created",
            resource_type="service_slo",
            resource_id=slo.id,
            user_id=user.id,
            details={"organization_id": organization_id, "service_id": service_id, "slo_type": slo_type},
        )
        await self.session.commit()
        return slo

    async def list_slos(self, user, org_context, service_id):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        return await self.slo_repo.list_for_service(service_id, organization_id)

    async def delete_slo(self, user, org_context, slo_id):
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        slo = await self.slo_repo.get_for_org(slo_id, organization_id)
        if slo is None:
            raise NexoraException("SLO not found.", status_code=404)
        await self.session.delete(slo)
        await self.audit_repo.log(
            action="service_slo_deleted",
            resource_type="service_slo",
            resource_id=slo_id,
            user_id=user.id,
            details={"organization_id": organization_id},
        )
        await self.session.commit()

    # --------------------------------------------------------- data gathering
    async def _gather(self, organization_id: str, service_name: str):
        assignments = [
            a
            for a in await self.assignment_repo.list_for_org(organization_id, limit=2000)
            if a.service_name == service_name
        ]
        alerts = [
            a
            for a in (await self.alert_repo.list_for_org(organization_id, limit=2000))[0]
            if a.service == service_name
        ]
        incidents_all, _ = await self.incident_repo.list_for_org(organization_id, limit=2000)
        incidents_map = {i.id: i for i in incidents_all}
        assignment_by_incident = {a.incident_id: a for a in assignments}
        incident_ids = set(assignment_by_incident.keys()) | {
            a.incident_id for a in alerts if a.incident_id
        }
        return assignments, alerts, incidents_map, assignment_by_incident, incident_ids

    def _downtime_intervals(self, incident_ids, incidents_map, assignment_by_incident, now):
        intervals: list[tuple[datetime, datetime]] = []
        per_incident: dict[str, tuple[datetime, datetime]] = {}
        for iid in incident_ids:
            inc = incidents_map.get(iid)
            if inc is None:
                continue
            asg = assignment_by_incident.get(iid)
            start = _aware(asg.assigned_at) if asg else _aware(inc.created_at)
            if asg and asg.resolved_at:
                end = _aware(asg.resolved_at)
            elif inc.status == IncidentInvestigationStatus.COMPLETED.value:
                end = _aware(inc.updated_at)
            else:
                end = now
            start = start or now
            end = end or now
            if end < start:
                end = start
            intervals.append((start, end))
            per_incident[iid] = (start, end)
        return intervals, per_incident

    @staticmethod
    def _downtime_within(intervals, days, now):
        ws = now - timedelta(days=days)
        clipped = [(max(s, ws), min(e, now)) for s, e in intervals]
        return _merge_minutes(clipped)

    def _alert_downtime_within(self, alerts, days, now):
        ws = now - timedelta(days=days)
        spans = []
        for a in alerts:
            s = _aware(a.first_seen_at) or now
            e = _aware(a.last_seen_at) or now
            spans.append((max(s, ws), min(e, now)))
        return _merge_minutes(spans)

    # ------------------------------------------------------------- the report
    async def health_report(self, user, org_context, service_id) -> ServiceHealthReport:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        service = await self.service_repo.get_for_org(service_id, organization_id)
        if service is None:
            raise NexoraException("Service not found.", status_code=404)
        slos = await self.slo_repo.list_for_service(service_id, organization_id)
        report = await self._compute(organization_id, service, slos, full=True)

        await self.audit_repo.log(
            action="service_health_viewed",
            resource_type="service",
            resource_id=service_id,
            user_id=user.id,
            details={"organization_id": organization_id, "health_score": report.health_score},
        )
        await self.session.commit()
        return report

    async def overview(self, user, org_context) -> ServiceHealthOverview:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        services = await self.service_repo.list_for_org(organization_id)
        summaries: list[ServiceHealthSummary] = []
        for svc in services:
            slos = await self.slo_repo.list_for_service(svc.id, organization_id)
            r = await self._compute(organization_id, svc, slos, full=False)
            summaries.append(
                ServiceHealthSummary(
                    service_id=svc.id,
                    name=svc.name,
                    tier=svc.tier,
                    owner_team=svc.owner_team,
                    health_score=r.health_score,
                    availability_30d=next((w.availability_percentage for w in r.availability if w.window == "30d"), 100.0),
                    error_budget_remaining_percentage=r.error_budget.remaining_percentage if r.error_budget else None,
                    burn_rate=r.burn_rate.burn_rate if r.burn_rate else 0.0,
                    burn_status=r.burn_rate.status if r.burn_rate else "NORMAL",
                    open_incidents=r.open_incidents,
                )
            )
        await self.audit_repo.log(
            action="service_health_overview_viewed",
            resource_type="service",
            resource_id=organization_id,
            user_id=user.id,
            details={"organization_id": organization_id, "services": len(summaries)},
        )
        await self.session.commit()
        scores = [s.health_score for s in summaries]
        return ServiceHealthOverview(
            services=summaries,
            average_health_score=round(sum(scores) / len(scores)) if scores else None,
            services_at_risk=sum(1 for s in summaries if s.burn_status != "NORMAL" or s.health_score < 90),
        )

    async def _compute(self, organization_id, service, slos, *, full: bool) -> ServiceHealthReport:
        now = _now()
        assignments, alerts, incidents_map, asg_by_inc, incident_ids = await self._gather(
            organization_id, service.name
        )
        intervals, per_incident = self._downtime_intervals(incident_ids, incidents_map, asg_by_inc, now)

        def avail(days):
            wmin = days * 24 * 60
            dt = self._downtime_within(intervals, days, now)
            return max(0.0, min(100.0, (wmin - dt) / wmin * 100.0)), dt

        a24, dt24 = avail(1)
        a7, _ = avail(7)
        a30, _ = avail(30)
        availability = [
            AvailabilityWindow(window="24h", availability_percentage=round(a24, 4), downtime_minutes=round(dt24, 2)),
            AvailabilityWindow(window="7d", availability_percentage=round(a7, 4), downtime_minutes=round(self._downtime_within(intervals, 7, now), 2)),
            AvailabilityWindow(window="30d", availability_percentage=round(a30, 4), downtime_minutes=round(self._downtime_within(intervals, 30, now), 2)),
        ]

        # Primary availability SLO drives the error budget + burn rate.
        avail_slo = next(
            (s for s in slos if s.slo_type == SLOType.AVAILABILITY.value and s.is_active), None
        )
        target = avail_slo.target_percentage if avail_slo else 99.9
        window_days = avail_slo.window_days if avail_slo else 30
        wmin = window_days * 24 * 60
        allowed = wmin * (1 - target / 100.0)
        consumed = self._downtime_within(intervals, window_days, now)
        remaining = allowed - consumed
        remaining_pct = (remaining / allowed * 100.0) if allowed > 0 else None
        error_budget = ErrorBudget(
            target_percentage=target,
            window_days=window_days,
            allowed_downtime_minutes=round(allowed, 2),
            consumed_minutes=round(consumed, 2),
            remaining_minutes=round(remaining, 2),
            remaining_percentage=_round(remaining_pct),
        )

        allowed_unavail = 1 - target / 100.0
        observed_24h = dt24 / 1440.0
        burn = (observed_24h / allowed_unavail) if allowed_unavail > 0 else 0.0
        burn_status = "CRITICAL" if burn >= 10 else "WARNING" if burn >= 2 else "NORMAL"
        burn_rate = BurnRate(
            burn_rate=round(burn, 2),
            status=burn_status,
            downtime_last_24h_minutes=round(dt24, 2),
            description=(
                f"{round(burn, 1)}x error-budget burn over the last 24h"
                if burn > 0
                else "No budget burn over the last 24h"
            ),
        )

        # Prediction.
        if remaining <= 0:
            prediction = SLOPrediction(
                will_breach=True, days_to_exhaustion=0.0,
                message=f"{service.name} has already exhausted its {window_days}-day error budget.",
            )
        elif dt24 > 0:
            days = remaining / dt24
            prediction = SLOPrediction(
                will_breach=days < window_days,
                days_to_exhaustion=round(days, 1),
                projected_exhaustion_at=now + timedelta(days=min(days, 3650)),
                message=(
                    f"At current burn rate, {service.name} will exhaust its "
                    f"{window_days}-day error budget in {round(days, 1)} days."
                ),
            )
        else:
            prediction = SLOPrediction(
                will_breach=False,
                message=f"Burn rate is stable; no projected SLO breach for {service.name}.",
            )

        # Per-SLO compliance.
        compliance = [self._slo_compliance(s, intervals, alerts, now, burn_status) for s in slos]

        open_incidents = sum(1 for a in assignments if a.state != "RESOLVED")

        # MTTA / MTTR for this service.
        def _mins(a, end_attr):
            end = _aware(getattr(a, end_attr, None))
            start = _aware(a.assigned_at)
            return max(0.0, (end - start).total_seconds() / 60.0) if (end and start) else None

        ttas = [v for v in (_mins(a, "acknowledged_at") for a in assignments) if v is not None]
        ttrs = [v for v in (_mins(a, "resolved_at") for a in assignments) if v is not None]
        mtta = round(sum(ttas) / len(ttas), 1) if ttas else None
        mttr = round(sum(ttrs) / len(ttrs), 1) if ttrs else None

        health_score = self._health_score(a30, burn_status, open_incidents)

        report = ServiceHealthReport(
            service_id=service.id,
            name=service.name,
            tier=service.tier,
            owner_team=service.owner_team,
            health_score=health_score,
            availability=availability,
            error_budget=error_budget,
            burn_rate=burn_rate,
            slo_compliance=compliance,
            prediction=prediction,
            open_incidents=open_incidents,
            mtta_minutes=mtta,
            mttr_minutes=mttr,
        )

        if full:
            ws30 = now - timedelta(days=30)
            corr_incidents = []
            for iid in incident_ids:
                inc = incidents_map.get(iid)
                if inc is None:
                    continue
                s, e = per_incident.get(iid, (now, now))
                dmin = _merge_minutes([(max(s, ws30), min(e, now))])
                corr_incidents.append(
                    CorrelatedIncident(
                        incident_id=inc.id,
                        title=inc.title,
                        severity=inc.severity,
                        status=inc.status,
                        downtime_minutes=round(dmin, 2),
                        created_at=inc.created_at,
                    )
                )
            corr_incidents.sort(key=lambda c: c.created_at, reverse=True)
            report.correlated_incidents = corr_incidents[:10]
            report.correlated_alerts = [
                CorrelatedAlert(
                    id=a.id,
                    alert_name=a.alert_name,
                    severity=a.severity,
                    occurrence_count=a.occurrence_count,
                    last_seen_at=a.last_seen_at,
                )
                for a in sorted(alerts, key=lambda x: _aware(x.last_seen_at) or now, reverse=True)[:10]
            ]
            report.correlated_deployments = await self._recent_deployments(organization_id, ws30)

        return report

    def _slo_compliance(self, slo, intervals, alerts, now, burn_status) -> SLOComplianceItem:
        base = dict(
            slo_id=slo.id,
            name=slo.name,
            slo_type=slo.slo_type,
            target_percentage=slo.target_percentage,
            window_days=slo.window_days,
            latency_percentile=slo.latency_percentile,
            threshold_ms=slo.threshold_ms,
        )
        if slo.slo_type == SLOType.AVAILABILITY.value:
            wmin = slo.window_days * 24 * 60
            dt = self._downtime_within(intervals, slo.window_days, now)
            observed = max(0.0, min(100.0, (wmin - dt) / wmin * 100.0))
            compliant = observed >= slo.target_percentage
            status = "HEALTHY" if compliant else "BREACHED"
            if compliant and burn_status != "NORMAL":
                status = "AT_RISK"
            return SLOComplianceItem(observed_value=round(observed, 4), compliant=compliant, status=status, **base)
        if slo.slo_type == SLOType.ERROR_RATE.value:
            wmin = slo.window_days * 24 * 60
            bad = self._alert_downtime_within(alerts, slo.window_days, now)
            observed = max(0.0, min(100.0, (wmin - bad) / wmin * 100.0))
            compliant = observed >= slo.target_percentage
            status = "HEALTHY" if compliant else "BREACHED"
            if compliant and burn_status != "NORMAL":
                status = "AT_RISK"
            return SLOComplianceItem(observed_value=round(observed, 4), compliant=compliant, status=status, **base)
        # LATENCY — no time-series metric store; surface target + any latency alerts.
        latency_firing = any(
            (a.status == MonitoringAlertStatus.FIRING.value)
            and any(h in (a.alert_name or "").lower() for h in _LATENCY_HINTS)
            for a in alerts
        )
        return SLOComplianceItem(
            observed_value=None,
            compliant=None,
            status="AT_RISK" if latency_firing else "NO_DATA",
            p50_ms=None,
            p95_ms=None,
            p99_ms=None,
            **base,
        )

    @staticmethod
    def _health_score(availability_30d, burn_status, open_incidents) -> int:
        score = availability_30d
        if burn_status == "CRITICAL":
            score = min(score, 50)
        elif burn_status == "WARNING":
            score = min(score, 80)
        score -= open_incidents * 3
        return int(max(0, min(100, round(score))))

    async def _recent_deployments(self, organization_id, since) -> list[CorrelatedDeployment]:
        stmt = (
            select(DeploymentRun)
            .where(
                DeploymentRun.organization_id == organization_id,
                DeploymentRun.created_at >= since,
            )
            .order_by(DeploymentRun.created_at.desc())
            .limit(10)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [
            CorrelatedDeployment(
                id=d.id, status=d.status, environment=d.environment, created_at=d.created_at
            )
            for d in rows
        ]
