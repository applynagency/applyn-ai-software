"""Sprint 45B - Executive Reliability Dashboard.

A read-only aggregation layer that rolls the platform's reliability intelligence
into a single executive view for CTOs and engineering leaders. It composes:

* 42C Service Health & SLO  -> availability, SLO compliance, error budget,
                               MTTA/MTTR, services-at-risk (via _compute).
* 40A Incident history      -> incident totals + trends.
* 41D/deployment runs       -> deployment success rate + rollback rate + trends.
* 43A Capacity forecasts    -> capacity resources / at-risk.
* 43B Cost optimization     -> monthly spend + potential savings.
* 44B Dependency graph      -> largest blast radius + per-incident exposure.
* 44C Change-failure        -> highest-risk services.

Everything is deterministic and explainable: the 0-100 Reliability Score is a
weighted blend of inspectable sub-scores. Views: organization / team / service.
Trends are produced for 7d / 30d / 90d. Nothing here mutates data.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NexoraException
from app.models.deployment import DeploymentStatus
from app.repositories.audit import AuditLogRepository
from app.repositories.capacity import CapacityForecastRepository
from app.repositories.change_failure import ChangeFailurePredictionRepository
from app.repositories.cost_optimization import CostOptimizationRepository
from app.repositories.deployment import DeploymentRunRepository
from app.repositories.incident import (
    IncidentInvestigationRepository,
    MonitoringAlertRepository,
)
from app.repositories.oncall import IncidentAssignmentRepository
from app.repositories.slo import ServiceRepository, ServiceSLORepository
from app.schemas.reliability_dashboard import (
    DashboardMetrics,
    ExecutiveSummaryResponse,
    ReliabilityDashboardResponse,
    RiskService,
    ScoreComponent,
    TrendBucket,
    TrendSeries,
)
from app.services.document_export import render_html, render_pdf
from app.services.graph import GraphService
from app.services.service_health import ServiceHealthService
from app.tenancy.permissions import can_read_ai_teams

logger = structlog.get_logger(__name__)

_SUCCESS = {DeploymentStatus.DEPLOYED.value}
_ROLLBACK = {DeploymentStatus.ROLLED_BACK.value, DeploymentStatus.ROLLBACK_IN_PROGRESS.value}
_FAILED = {DeploymentStatus.FAILED.value}


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt):
    if dt is None:
        return None
    return dt if getattr(dt, "tzinfo", None) else dt.replace(tzinfo=UTC)


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _avg(values: list[float]) -> float | None:
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def _grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


class ReliabilityDashboardService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit_repo = AuditLogRepository(session)
        self.service_repo = ServiceRepository(session)
        self.slo_repo = ServiceSLORepository(session)
        self.inv_repo = IncidentInvestigationRepository(session)
        self.assignment_repo = IncidentAssignmentRepository(session)
        self.alert_repo = MonitoringAlertRepository(session)
        self.graph = GraphService(session)
        self.pred_repo = ChangeFailurePredictionRepository(session)
        self.cost_repo = CostOptimizationRepository(session)
        self.forecast_repo = CapacityForecastRepository(session)
        self.run_repo = DeploymentRunRepository(session)
        self.health = ServiceHealthService(session)

    def _ensure_read(self, user, org_context) -> None:
        if not user.is_superuser and (
            not org_context.role or not can_read_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    # ------------------------------------------------------------- public API
    async def dashboard(self, user, org_context, *, scope, scope_value, window_days):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        scope, scope_value, window_days = self._validate(scope, scope_value, window_days)
        result = await self._build(organization_id, scope, scope_value, window_days)
        await self.audit_repo.log(
            action="reliability_dashboard_viewed",
            resource_type="reliability_dashboard",
            resource_id=None,
            user_id=user.id,
            details={"organization_id": organization_id, "scope": scope,
                     "scope_value": scope_value, "reliability_score": result.reliability_score},
        )
        await self.session.commit()
        return result

    async def summary(self, user, org_context, *, scope, scope_value, window_days):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        scope, scope_value, window_days = self._validate(scope, scope_value, window_days)
        dash = await self._build(organization_id, scope, scope_value, window_days)
        summ = self._summary_from(dash)
        await self.audit_repo.log(
            action="reliability_summary_generated",
            resource_type="reliability_dashboard",
            resource_id=None,
            user_id=user.id,
            details={"organization_id": organization_id, "scope": scope,
                     "reliability_score": dash.reliability_score},
        )
        await self.session.commit()
        return summ

    async def export(self, user, org_context, *, scope, scope_value, window_days, fmt):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        scope, scope_value, window_days = self._validate(scope, scope_value, window_days)
        dash = await self._build(organization_id, scope, scope_value, window_days)
        summ = self._summary_from(dash)
        markdown = self._render_markdown(dash, summ)
        fmt = (fmt or "pdf").lower()
        scope_tag = (scope_value or scope).replace(" ", "-").lower()
        if fmt == "pdf":
            content, media_type, filename = render_pdf(markdown), "application/pdf", f"reliability-{scope_tag}.pdf"
        elif fmt == "html":
            content = render_html("Executive Reliability Report", markdown).encode("utf-8")
            media_type, filename = "text/html", f"reliability-{scope_tag}.html"
        elif fmt in ("markdown", "md"):
            content, media_type, filename = markdown.encode("utf-8"), "text/markdown", f"reliability-{scope_tag}.md"
        else:
            raise NexoraException("Unsupported export format. Use pdf, html, or markdown.", status_code=400)
        await self.audit_repo.log(
            action="reliability_dashboard_exported",
            resource_type="reliability_dashboard",
            resource_id=None,
            user_id=user.id,
            details={"organization_id": organization_id, "scope": scope, "format": fmt},
        )
        await self.session.commit()
        return content, media_type, filename

    # -------------------------------------------------------------- internals
    @staticmethod
    def _validate(scope, scope_value, window_days):
        scope = (scope or "organization").lower()
        if scope not in ("organization", "team", "service"):
            raise NexoraException("scope must be organization, team, or service.", status_code=400)
        if scope in ("team", "service") and not scope_value:
            raise NexoraException(f"{scope} scope requires a value.", status_code=400)
        if window_days not in (7, 30, 90):
            window_days = 30
        return scope, scope_value, window_days

    async def _scoped_services(self, organization_id, scope, scope_value):
        services = await self.service_repo.list_for_org(organization_id)
        if scope == "team":
            return [s for s in services if (s.owner_team or "").lower() == scope_value.lower()]
        if scope == "service":
            return [s for s in services if s.name.lower() == scope_value.lower()]
        return services

    async def _build(self, organization_id, scope, scope_value, window_days) -> ReliabilityDashboardResponse:
        now = _now()
        services = await self._scoped_services(organization_id, scope, scope_value)
        scoped_names = {s.name for s in services}
        in_scope_all = scope == "organization"

        # --- per-service health (42C) ---------------------------------------
        reports = []
        for svc in services:
            slos = await self.slo_repo.list_for_service(svc.id, organization_id)
            reports.append((svc, await self.health._compute(organization_id, svc, slos, full=False)))

        avail = _avg([
            next((w.availability_percentage for w in r.availability if w.window == "30d"), None)
            for _, r in reports
        ])
        budgets = [r.error_budget.remaining_percentage for _, r in reports
                   if r.error_budget and r.error_budget.remaining_percentage is not None]
        error_budget = _avg(budgets)
        mtta = _avg([r.mtta_minutes for _, r in reports])
        mttr = _avg([r.mttr_minutes for _, r in reports])
        services_at_risk = sum(1 for _, r in reports if r.health_score < 90 or (r.burn_rate and r.burn_rate.status != "NORMAL"))
        open_incidents = sum(r.open_incidents for _, r in reports)

        # SLO compliance: among services with an availability budget, fraction
        # currently meeting their target.
        compliant = 0
        budget_services = 0
        for _, r in reports:
            if r.error_budget and r.error_budget.remaining_percentage is not None:
                budget_services += 1
                if r.error_budget.remaining_percentage > 0:
                    compliant += 1
        slo_compliance = round(100.0 * compliant / budget_services, 2) if budget_services else None

        # --- incidents (40A) -------------------------------------------------
        incidents, svc_map = await self._incidents(organization_id)
        win_start = now - timedelta(days=window_days)

        def _in_scope_incident(inc):
            if in_scope_all:
                return True
            svc = svc_map.get(inc.id)
            return svc in scoped_names

        scoped_incidents = [i for i in incidents if _in_scope_incident(i)]
        total_incidents = sum(1 for i in scoped_incidents if (_aware(i.created_at) or now) >= win_start)

        # --- deployments (41D / runs) ---------------------------------------
        runs, _ = await self.run_repo.list_by_organization(organization_id, limit=2000)
        win_runs = [r for r in runs if (_aware(r.created_at) or now) >= win_start]
        total_deploys = len(win_runs)
        successes = sum(1 for r in win_runs if r.status in _SUCCESS)
        rollbacks = sum(1 for r in win_runs if r.status in _ROLLBACK)
        terminal = sum(1 for r in win_runs if r.status in _SUCCESS | _ROLLBACK | _FAILED)
        deploy_success_rate = round(100.0 * successes / terminal, 2) if terminal else None
        rollback_rate = round(100.0 * rollbacks / terminal, 2) if terminal else None

        # --- capacity (43A) --------------------------------------------------
        forecasts = await self.forecast_repo.list_recent(organization_id, limit=500)
        if not in_scope_all:
            forecasts = [f for f in forecasts if (f.service or "") in scoped_names]
        capacity_at_risk = sum(1 for f in forecasts if (f.status or "HEALTHY") != "HEALTHY")

        # --- cost (43B) ------------------------------------------------------
        cost = await self.cost_repo.latest(organization_id)
        monthly_cost = round(cost.current_cost, 2) if cost else None
        potential_savings = round(cost.potential_savings, 2) if cost else None

        # --- blast radius (44B) ---------------------------------------------
        graph = await self.graph.service_adjacency(organization_id)
        all_services = await self.service_repo.list_for_org(organization_id)
        name_by_id = {s.id: s.name for s in all_services}
        id_by_name = {s.name: s.id for s in all_services}
        largest_blast, largest_blast_service = 0, None
        for svc in services:
            _, transitive = graph.dependents(svc.id)
            if len(transitive) > largest_blast:
                largest_blast, largest_blast_service = len(transitive), svc.name

        # --- highest risk services (44C, fallback 42C) ----------------------
        highest_risk = await self._highest_risk(organization_id, scoped_names, in_scope_all, reports)

        metrics = DashboardMetrics(
            availability_30d=avail,
            slo_compliance_percentage=slo_compliance,
            error_budget_remaining_percentage=error_budget,
            services_total=len(services),
            services_at_risk=services_at_risk,
            mtta_minutes=mtta,
            mttr_minutes=mttr,
            total_incidents=total_incidents,
            open_incidents=open_incidents,
            total_deployments=total_deploys,
            deployment_success_rate=deploy_success_rate,
            rollback_rate=rollback_rate,
            capacity_resources=len(forecasts),
            capacity_at_risk=capacity_at_risk,
            monthly_cost=monthly_cost,
            potential_savings=potential_savings,
            largest_blast_radius=largest_blast,
            largest_blast_radius_service=largest_blast_service,
            highest_risk_services=highest_risk,
        )

        score, breakdown = self._score(metrics, len(services))

        # --- trends (7d / 30d / 90d) ----------------------------------------
        trends = {}
        for w in (7, 30, 90):
            trends[w] = self._trend(
                w, now, scoped_incidents, svc_map, id_by_name, graph,
                runs if in_scope_all else win_runs, in_scope_all, runs, cost, forecasts,
            )

        return ReliabilityDashboardResponse(
            scope=scope,
            scope_value=scope_value,
            window_days=window_days,
            reliability_score=int(round(score)),
            score_grade=_grade(score),
            score_breakdown=breakdown,
            metrics=metrics,
            trends_7d=trends[7],
            trends_30d=trends[30],
            trends_90d=trends[90],
            generated_at=now,
        )

    async def _incidents(self, organization_id):
        incidents, _ = await self.inv_repo.list_for_org(organization_id, limit=2000)
        mapping: dict[str, str] = {}
        assignments = await self.assignment_repo.list_for_org(organization_id, limit=2000)
        for a in assignments:
            if a.service_name:
                mapping[a.incident_id] = a.service_name
        alerts, _ = await self.alert_repo.list_for_org(organization_id, limit=2000)
        for al in alerts:
            if al.incident_id and al.incident_id not in mapping and al.service:
                mapping[al.incident_id] = al.service
        return incidents, mapping

    async def _highest_risk(self, organization_id, scoped_names, in_scope_all, reports):
        preds = await self.pred_repo.list_for_org(organization_id, limit=300)
        if not in_scope_all:
            preds = [p for p in preds if (p.service or "") in scoped_names]
        if preds:
            by_service: dict[str, int] = {}
            for p in preds:
                key = p.service or "(unknown)"
                by_service[key] = max(by_service.get(key, 0), p.failure_probability)
            ranked = sorted(by_service.items(), key=lambda kv: kv[1], reverse=True)[:5]
            return [RiskService(service=s, score=float(v), basis="change_failure_prediction")
                    for s, v in ranked]
        ranked = sorted(reports, key=lambda r: r[1].health_score)[:5]
        return [RiskService(service=s.name, score=float(100 - r.health_score), basis="service_health")
                for s, r in ranked if r.health_score < 100]

    # ------------------------------------------------------------- scoring
    def _score(self, m: DashboardMetrics, n_services: int):
        comps: list[ScoreComponent] = []

        def add(name, score, weight, detail):
            score = _clamp(score)
            comps.append(ScoreComponent(name=name, score=round(score, 1), weight=weight,
                                        points=round(score * weight, 2), detail=detail))

        # Availability: 95% -> 0, 100% -> 100 (neutral 100 when no data).
        if m.availability_30d is not None:
            a = _clamp((m.availability_30d - 95.0) / 5.0 * 100.0)
            add("Availability", a, 0.25, f"30-day availability {m.availability_30d}%")
        else:
            add("Availability", 100, 0.25, "No availability data; treated as neutral")

        add("SLO compliance",
            m.slo_compliance_percentage if m.slo_compliance_percentage is not None else 100,
            0.15,
            f"{m.slo_compliance_percentage}% of SLO-tracked services in budget"
            if m.slo_compliance_percentage is not None else "No SLOs tracked; neutral")

        add("Error budget",
            m.error_budget_remaining_percentage if m.error_budget_remaining_percentage is not None else 100,
            0.15,
            f"{m.error_budget_remaining_percentage}% error budget remaining (avg)"
            if m.error_budget_remaining_percentage is not None else "No error budget tracked; neutral")

        # Incident frequency: penalize incidents per service over the window.
        per_service = m.total_incidents / max(1, n_services or 1)
        inc_score = _clamp(100 - per_service * 20)
        add("Incident frequency", inc_score, 0.15,
            f"{m.total_incidents} incident(s) across {n_services or 1} service(s)")

        # MTTR: <=30m -> 100, +1 point lost per ~6 min beyond 30m.
        if m.mttr_minutes is not None:
            mttr_score = _clamp(100 - max(0.0, m.mttr_minutes - 30.0) / 6.0)
            add("MTTR", mttr_score, 0.10, f"Mean time to recover {round(m.mttr_minutes)} min")
        else:
            add("MTTR", 100, 0.10, "No resolved incidents; neutral")

        add("Deployment success",
            m.deployment_success_rate if m.deployment_success_rate is not None else 100,
            0.15,
            f"{m.deployment_success_rate}% deploy success rate"
            if m.deployment_success_rate is not None else "No deployments in window; neutral")

        if m.rollback_rate is not None:
            add("Rollback rate", _clamp(100 - m.rollback_rate), 0.05, f"{m.rollback_rate}% rollback rate")
        else:
            add("Rollback rate", 100, 0.05, "No deployments in window; neutral")

        total = sum(c.points for c in comps)
        return total, comps

    # ------------------------------------------------------------- trends
    def _trend(self, window_days, now, scoped_incidents, svc_map, id_by_name,
               graph, scoped_runs, in_scope_all, all_runs, cost, forecasts) -> TrendSeries:
        bucket_days = max(1, window_days // 10)
        n_buckets = window_days // bucket_days
        start = now - timedelta(days=window_days)
        buckets: list[TrendBucket] = []
        for i in range(n_buckets):
            b_start = start + timedelta(days=i * bucket_days)
            b_end = b_start + timedelta(days=bucket_days)
            inc = [x for x in scoped_incidents if b_start <= (_aware(x.created_at) or now) < b_end]
            dep = [r for r in scoped_runs if b_start <= (_aware(r.created_at) or now) < b_end]
            failed = sum(1 for r in dep if r.status in _FAILED | _ROLLBACK)
            terminal = sum(1 for r in dep if r.status in _SUCCESS | _FAILED | _ROLLBACK)
            succ = sum(1 for r in dep if r.status in _SUCCESS)
            sr = round(100.0 * succ / terminal, 1) if terminal else None
            # Max blast radius among incidents in this bucket.
            max_blast = 0
            for x in inc:
                svc = svc_map.get(x.id)
                sid = id_by_name.get(svc) if svc else None
                if sid:
                    _, transitive = graph.dependents(sid)
                    max_blast = max(max_blast, len(transitive))
            cap_risk = sum(1 for f in forecasts
                           if f.created_at and b_start <= (_aware(f.created_at) or now) < b_end
                           and (f.status or "HEALTHY") != "HEALTHY")
            bucket_cost = None
            if cost and cost.created_at and b_start <= (_aware(cost.created_at) or now) < b_end:
                bucket_cost = round(cost.current_cost, 2)
            buckets.append(TrendBucket(
                period_start=b_start.strftime("%Y-%m-%d"),
                incidents=len(inc),
                deployments=len(dep),
                failed_deployments=failed,
                deployment_success_rate=sr,
                cost=bucket_cost,
                capacity_at_risk=cap_risk,
                max_blast_radius=max_blast,
            ))
        return TrendSeries(window_days=window_days, bucket_days=bucket_days, buckets=buckets)

    # ------------------------------------------------------------- summary
    def _summary_from(self, d: ReliabilityDashboardResponse) -> ExecutiveSummaryResponse:
        m = d.metrics
        scope_label = d.scope if d.scope == "organization" else f"{d.scope} '{d.scope_value}'"
        grade_word = {"A": "excellent", "B": "good", "C": "fair", "D": "poor", "F": "critical"}[d.score_grade]

        summary = (
            f"Reliability for {scope_label} scores {d.reliability_score}/100 (grade {d.score_grade}, {grade_word}). "
            f"Across {m.services_total} service(s), {m.services_at_risk} are currently at risk. "
            f"Over the last {d.window_days} days there were {m.total_incidents} incident(s) "
            f"({m.open_incidents} open), "
            + (f"with a mean time to recover of {round(m.mttr_minutes)} min. "
               if m.mttr_minutes is not None else "with no resolved incidents to measure recovery time. ")
            + (f"Deployment success rate is {m.deployment_success_rate}% "
               f"with a {m.rollback_rate}% rollback rate."
               if m.deployment_success_rate is not None else "No deployments occurred in the window.")
        )

        highlights, risks, recs = [], [], []
        if m.availability_30d is not None:
            highlights.append(f"30-day availability: {m.availability_30d}%.")
        if m.deployment_success_rate is not None and m.deployment_success_rate >= 95:
            highlights.append(f"Strong deployment success rate ({m.deployment_success_rate}%).")
        if m.monthly_cost is not None:
            highlights.append(f"Monthly spend ${round(m.monthly_cost):,} with ${round(m.potential_savings or 0):,} identified savings.")

        if m.services_at_risk:
            risks.append(f"{m.services_at_risk} service(s) below healthy thresholds.")
        if m.error_budget_remaining_percentage is not None and m.error_budget_remaining_percentage < 25:
            risks.append(f"Error budget low ({m.error_budget_remaining_percentage}% remaining on average).")
        if m.rollback_rate is not None and m.rollback_rate > 10:
            risks.append(f"Elevated rollback rate ({m.rollback_rate}%).")
        if m.capacity_at_risk:
            risks.append(f"{m.capacity_at_risk} capacity resource(s) approaching saturation.")
        if m.largest_blast_radius and m.largest_blast_radius_service:
            risks.append(f"'{m.largest_blast_radius_service}' has the largest blast radius "
                         f"({m.largest_blast_radius} dependent service(s)).")
        for r in m.highest_risk_services[:3]:
            risks.append(f"High-risk service '{r.service}' ({round(r.score)}% risk).")

        worst = min(d.score_breakdown, key=lambda c: c.score) if d.score_breakdown else None
        if worst and worst.score < 80:
            recs.append(f"Prioritize improving {worst.name.lower()} - lowest-scoring dimension ({round(worst.score)}/100).")
        if m.potential_savings:
            recs.append(f"Capture ${round(m.potential_savings):,}/mo in identified cost savings.")
        if m.highest_risk_services:
            recs.append(f"Add canary rollouts / extra review for high-risk service '{m.highest_risk_services[0].service}'.")
        if not recs:
            recs.append("Maintain current practices; no critical reliability gaps detected.")

        return ExecutiveSummaryResponse(
            scope=d.scope, scope_value=d.scope_value,
            reliability_score=d.reliability_score, score_grade=d.score_grade,
            summary=summary, highlights=highlights, risks=risks, recommendations=recs,
            generated_at=d.generated_at,
        )

    # ------------------------------------------------------------- markdown
    def _render_markdown(self, d: ReliabilityDashboardResponse, s: ExecutiveSummaryResponse) -> str:
        m = d.metrics
        scope_label = "Organization" if d.scope == "organization" else f"{d.scope.title()}: {d.scope_value}"
        L = [
            "# Executive Reliability Report",
            f"{scope_label}",
            f"Reliability Score: {d.reliability_score}/100 (Grade {d.score_grade})",
            f"Window: last {d.window_days} days | Generated: {d.generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "## Executive Summary",
            s.summary,
            "",
            "## Reliability Score Breakdown",
        ]
        for c in d.score_breakdown:
            L.append(f"- {c.name}: {c.score}/100 (weight {int(c.weight*100)}%, +{c.points} pts) - {c.detail}")
        L += [
            "",
            "## Key Metrics",
            f"- Availability (30d): {m.availability_30d if m.availability_30d is not None else 'n/a'}%",
            f"- SLO compliance: {m.slo_compliance_percentage if m.slo_compliance_percentage is not None else 'n/a'}%",
            f"- Error budget remaining (avg): {m.error_budget_remaining_percentage if m.error_budget_remaining_percentage is not None else 'n/a'}%",
            f"- MTTA: {round(m.mtta_minutes) if m.mtta_minutes is not None else 'n/a'} min | MTTR: {round(m.mttr_minutes) if m.mttr_minutes is not None else 'n/a'} min",
            f"- Incidents (window): {m.total_incidents} | Open: {m.open_incidents}",
            f"- Deployments: {m.total_deployments} | Success rate: {m.deployment_success_rate if m.deployment_success_rate is not None else 'n/a'}% | Rollback rate: {m.rollback_rate if m.rollback_rate is not None else 'n/a'}%",
            f"- Capacity resources: {m.capacity_resources} | At risk: {m.capacity_at_risk}",
            f"- Monthly cost: ${round(m.monthly_cost):,}" if m.monthly_cost is not None else "- Monthly cost: n/a",
            f"- Largest blast radius: {m.largest_blast_radius} dependents" + (f" ({m.largest_blast_radius_service})" if m.largest_blast_radius_service else ""),
            "",
            "## Highest-Risk Services",
        ]
        if m.highest_risk_services:
            for r in m.highest_risk_services:
                L.append(f"- {r.service}: {round(r.score)}% ({r.basis})")
        else:
            L.append("- None identified.")
        if s.risks:
            L += ["", "## Risks"] + [f"- {x}" for x in s.risks]
        if s.recommendations:
            L += ["", "## Recommendations"] + [f"- {x}" for x in s.recommendations]
        return "\n".join(L)
