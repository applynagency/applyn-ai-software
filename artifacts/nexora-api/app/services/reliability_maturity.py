"""Sprint 46A - Reliability Maturity Score Engine.

Computes an organization-wide Reliability Maturity Score (0-100) across seven
dimensions by reading existing platform intelligence (read-only). Each dimension
is scored deterministically from adoption + quality signals; the overall score is
a weighted blend. Assessments are persisted so trends can be reported over time.

Dimensions & weights
---------------------
    Incident response   0.20   (40A incidents, 42B assignments, 44A postmortems)
    Monitoring          0.15   (42A alerts, providers, proactive incidents, dedup)
    Deployment          0.15   (deployment runs, success/rollback, 44C predictions)
    SLO                 0.15   (42C SLO coverage, error budget, burn rate)
    On-call             0.15   (42B owners, schedules, escalation policies)
    Capacity            0.10   (43A metrics + forecasts)
    Cost optimization   0.10   (43B analysis + identified savings)

Maturity levels (score band): BEGINNER <20 | DEVELOPING <40 | MATURE <60 |
ADVANCED <80 | ELITE >=80. Never executes deployments or remediations.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NexoraException
from app.models.deployment import DeploymentStatus
from app.models.reliability_maturity import MaturityCategory, MaturityLevel
from app.repositories.audit import AuditLogRepository
from app.repositories.capacity import CapacityForecastRepository, CapacityMetricRepository
from app.repositories.change_failure import ChangeFailurePredictionRepository
from app.repositories.cost_optimization import CostOptimizationRepository
from app.repositories.deployment import DeploymentRunRepository
from app.repositories.incident import (
    IncidentInvestigationRepository,
    MonitoringAlertRepository,
)
from app.repositories.oncall import (
    EscalationPolicyRepository,
    IncidentAssignmentRepository,
    OnCallScheduleRepository,
    ServiceOwnerRepository,
)
from app.repositories.postmortem import PostmortemRepository
from app.repositories.reliability_maturity import (
    ReliabilityAssessmentRepository,
    ReliabilityScoreCategoryRepository,
)
from app.repositories.slo import ServiceRepository, ServiceSLORepository
from app.schemas.reliability_maturity import (
    AssessmentResponse,
    CategoryScore,
    CategoryTrend,
    Recommendation,
    ReliabilityDashboard,
    TrendPoint,
)
from app.services.service_health import ServiceHealthService
from app.tenancy.permissions import can_read_ai_teams

logger = structlog.get_logger(__name__)

_SUCCESS = {DeploymentStatus.DEPLOYED.value}
_ROLLBACK = {DeploymentStatus.ROLLED_BACK.value, DeploymentStatus.ROLLBACK_IN_PROGRESS.value}
_FAILED = {DeploymentStatus.FAILED.value}

_WEIGHTS = {
    MaturityCategory.INCIDENT_RESPONSE.value: 0.20,
    MaturityCategory.MONITORING.value: 0.15,
    MaturityCategory.DEPLOYMENT.value: 0.15,
    MaturityCategory.SLO.value: 0.15,
    MaturityCategory.ONCALL.value: 0.15,
    MaturityCategory.CAPACITY.value: 0.10,
    MaturityCategory.COST_OPTIMIZATION.value: 0.10,
}

_CATEGORY_LABEL = {
    MaturityCategory.INCIDENT_RESPONSE.value: "Incident response",
    MaturityCategory.MONITORING.value: "Monitoring",
    MaturityCategory.DEPLOYMENT.value: "Deployment",
    MaturityCategory.SLO.value: "SLO",
    MaturityCategory.ONCALL.value: "On-call",
    MaturityCategory.CAPACITY.value: "Capacity",
    MaturityCategory.COST_OPTIMIZATION.value: "Cost optimization",
}

_ADVICE = {
    MaturityCategory.MONITORING.value:
        "Connect more monitoring providers and ensure alerts auto-create incidents; enable alert deduplication.",
    MaturityCategory.INCIDENT_RESPONSE.value:
        "Assign every incident an owner, capture root-cause analysis, and write postmortems for major incidents.",
    MaturityCategory.DEPLOYMENT.value:
        "Raise deployment success rate with canary rollouts and run change-failure predictions before shipping.",
    MaturityCategory.SLO.value:
        "Define SLOs for all critical services and actively track error budgets and burn rate.",
    MaturityCategory.ONCALL.value:
        "Define service owners, on-call schedules, and escalation policies so incidents route automatically.",
    MaturityCategory.CAPACITY.value:
        "Ingest capacity metrics and generate forecasts to predict saturation before it impacts customers.",
    MaturityCategory.COST_OPTIMIZATION.value:
        "Run cost optimization analysis regularly and act on identified savings and rightsizing opportunities.",
}


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt):
    if dt is None:
        return None
    return dt if getattr(dt, "tzinfo", None) else dt.replace(tzinfo=UTC)


def _clamp(v: float) -> int:
    return int(round(max(0.0, min(100.0, v))))


def _level(score: float) -> str:
    if score < 20:
        return MaturityLevel.BEGINNER.value
    if score < 40:
        return MaturityLevel.DEVELOPING.value
    if score < 60:
        return MaturityLevel.MATURE.value
    if score < 80:
        return MaturityLevel.ADVANCED.value
    return MaturityLevel.ELITE.value


class _Cat:
    """Internal carrier for a computed category score."""
    __slots__ = ("category", "score", "detail", "signals")

    def __init__(self, category, score, detail, signals):
        self.category = category
        self.score = _clamp(score)
        self.detail = detail
        self.signals = signals


class ReliabilityMaturityService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit_repo = AuditLogRepository(session)
        self.assessment_repo = ReliabilityAssessmentRepository(session)
        self.category_repo = ReliabilityScoreCategoryRepository(session)
        # signal sources
        self.alert_repo = MonitoringAlertRepository(session)
        self.inv_repo = IncidentInvestigationRepository(session)
        self.assignment_repo = IncidentAssignmentRepository(session)
        self.pm_repo = PostmortemRepository(session)
        self.run_repo = DeploymentRunRepository(session)
        self.pred_repo = ChangeFailurePredictionRepository(session)
        self.service_repo = ServiceRepository(session)
        self.slo_repo = ServiceSLORepository(session)
        self.forecast_repo = CapacityForecastRepository(session)
        self.metric_repo = CapacityMetricRepository(session)
        self.cost_repo = CostOptimizationRepository(session)
        self.owner_repo = ServiceOwnerRepository(session)
        self.schedule_repo = OnCallScheduleRepository(session)
        self.escalation_repo = EscalationPolicyRepository(session)
        self.health = ServiceHealthService(session)

    def _ensure_read(self, user, org_context) -> None:
        if not user.is_superuser and (
            not org_context.role or not can_read_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    # --------------------------------------------------------------- public
    async def analyze(self, user, org_context) -> AssessmentResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)

        cats = await self._score_all(organization_id)
        overall = sum(c.score * _WEIGHTS[c.category] for c in cats)
        overall_i = int(round(overall))
        level = _level(overall_i)

        strengths, weaknesses = self._strengths_weaknesses(cats)
        recs = self._recommendations(cats)

        previous = await self.assessment_repo.latest(organization_id)
        prev_overall = previous.overall_score if previous else None
        details = {
            "category_scores": {c.category: c.score for c in cats},
            "weights": _WEIGHTS,
            "previous_overall_score": prev_overall,
            "delta_vs_previous": (overall_i - prev_overall) if prev_overall is not None else None,
        }
        summary = self._summary(overall_i, level, cats, prev_overall)

        assessment = await self.assessment_repo.create(
            organization_id=organization_id,
            overall_score=overall_i,
            maturity_level=level,
            summary=summary,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=[r.model_dump() for r in recs],
            details=details,
            created_by=user.id,
        )
        for c in cats:
            await self.category_repo.create(
                assessment_id=assessment.id,
                organization_id=organization_id,
                category=c.category,
                score=c.score,
                maturity_level=_level(c.score),
                weight=_WEIGHTS[c.category],
                detail=c.detail,
                signals=c.signals,
            )

        await self.audit_repo.log(
            action="reliability_assessment_created",
            resource_type="reliability_assessment",
            resource_id=assessment.id,
            user_id=user.id,
            details={"organization_id": organization_id, "overall_score": overall_i, "maturity_level": level},
        )
        await self.session.commit()
        return await self._to_response(assessment, cats=cats, recs=recs)

    async def list(self, user, org_context):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        return await self.assessment_repo.list_for_org(organization_id)

    async def get(self, user, org_context, assessment_id: str) -> AssessmentResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        assessment = await self.assessment_repo.get_for_org(assessment_id, organization_id)
        if assessment is None:
            raise NexoraException("Assessment not found.", status_code=404)
        categories = await self.category_repo.list_for_assessment(assessment_id, organization_id)
        return await self._to_response(assessment, category_rows=categories)

    async def dashboard(self, user, org_context) -> ReliabilityDashboard:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        assessments = await self.assessment_repo.list_for_org(organization_id, limit=100)
        latest_resp = None
        if assessments:
            latest = assessments[0]
            cats = await self.category_repo.list_for_assessment(latest.id, organization_id)
            latest_resp = await self._to_response(latest, category_rows=cats)

        ordered = list(reversed(assessments))  # ascending by created_at
        trend = [
            TrendPoint(date=_aware(a.created_at).strftime("%Y-%m-%d %H:%M"),
                       overall_score=a.overall_score, maturity_level=a.maturity_level)
            for a in ordered
        ]
        cat_series: dict[str, list[int]] = {c: [] for c in _WEIGHTS}
        for a in ordered:
            scores = (a.details or {}).get("category_scores", {})
            for c in _WEIGHTS:
                if c in scores:
                    cat_series[c].append(int(scores[c]))
        category_trends = [CategoryTrend(category=c, points=pts) for c, pts in cat_series.items() if pts]

        await self.audit_repo.log(
            action="reliability_maturity_dashboard_viewed",
            resource_type="reliability_assessment",
            resource_id=None,
            user_id=user.id,
            details={"organization_id": organization_id, "assessments": len(assessments)},
        )
        await self.session.commit()
        return ReliabilityDashboard(
            latest=latest_resp,
            assessments_count=len(assessments),
            trend=trend,
            category_trends=category_trends,
        )

    # ------------------------------------------------------------ scoring
    async def _score_all(self, organization_id) -> list[_Cat]:
        return [
            await self._score_monitoring(organization_id),
            await self._score_incident_response(organization_id),
            await self._score_deployment(organization_id),
            await self._score_slo(organization_id),
            await self._score_capacity(organization_id),
            await self._score_cost(organization_id),
            await self._score_oncall(organization_id),
        ]

    async def _score_monitoring(self, organization_id) -> _Cat:
        alerts, _ = await self.alert_repo.list_for_org(organization_id, limit=2000)
        providers = {a.provider for a in alerts if a.provider}
        proactive = sum(1 for a in alerts if a.incident_id)
        dedup = sum(1 for a in alerts if (a.occurrence_count or 1) > 1)
        recent = sum(1 for a in alerts if (_aware(a.last_seen_at) or _now()) >= _now() - timedelta(days=7))
        score = 0
        score += 35 if alerts else 0
        score += 20 if len(providers) >= 2 else (10 if len(providers) == 1 else 0)
        score += 25 if proactive else 0
        score += 10 if dedup else 0
        score += 10 if recent else 0
        signals = {"alerts": len(alerts), "providers": len(providers),
                   "proactive_incidents": proactive, "deduplicated": dedup, "recent_alerts": recent}
        detail = (f"{len(alerts)} alert(s) across {len(providers)} provider(s); "
                  f"{proactive} auto-created incident(s).") if alerts else \
                 "No monitoring alerts ingested yet."
        return _Cat(MaturityCategory.MONITORING.value, score, detail, signals)

    async def _score_incident_response(self, organization_id) -> _Cat:
        incidents, _ = await self.inv_repo.list_for_org(organization_id, limit=2000)
        assignments = await self.assignment_repo.list_for_org(organization_id, limit=2000)
        pms, pm_total = await self.pm_repo.list_for_org(organization_id, offset=0, limit=1)
        n = len(incidents)
        if n == 0:
            return _Cat(MaturityCategory.INCIDENT_RESPONSE.value, 50,
                        "No incidents recorded; response practice is unproven (neutral).",
                        {"incidents": 0, "assignments": len(assignments), "postmortems": pm_total})
        assigned_ids = {a.incident_id for a in assignments}
        acked = sum(1 for a in assignments if a.acknowledged_at)
        resolved = sum(1 for a in assignments if a.resolved_at)
        rca = sum(1 for i in incidents if (i.root_cause or "").strip())
        assigned_rate = len(assigned_ids & {i.id for i in incidents}) / n
        ack_rate = acked / n
        resolved_rate = resolved / n
        rca_rate = rca / n
        score = (assigned_rate * 20) + (ack_rate * 20) + (resolved_rate * 20) + (rca_rate * 20)
        score += 20 if pm_total else 0
        signals = {"incidents": n, "assigned_rate": round(assigned_rate, 2),
                   "acknowledged_rate": round(ack_rate, 2), "resolved_rate": round(resolved_rate, 2),
                   "rca_rate": round(rca_rate, 2), "postmortems": pm_total}
        detail = (f"{n} incident(s): {int(ack_rate*100)}% acknowledged, {int(resolved_rate*100)}% resolved, "
                  f"{int(rca_rate*100)}% with RCA; {pm_total} postmortem(s).")
        return _Cat(MaturityCategory.INCIDENT_RESPONSE.value, score, detail, signals)

    async def _score_deployment(self, organization_id) -> _Cat:
        runs, _ = await self.run_repo.list_by_organization(organization_id, limit=2000)
        preds = await self.pred_repo.list_for_org(organization_id, limit=200)
        terminal = [r for r in runs if r.status in _SUCCESS | _FAILED | _ROLLBACK]
        successes = sum(1 for r in terminal if r.status in _SUCCESS)
        rollbacks = sum(1 for r in terminal if r.status in _ROLLBACK)
        success_rate = (successes / len(terminal)) if terminal else None
        rollback_rate = (rollbacks / len(terminal)) if terminal else None
        score = 0
        score += 25 if runs else 0
        if success_rate is not None:
            score += success_rate * 35
            score += (1 - (rollback_rate or 0)) * 15
        score += 25 if preds else 0
        signals = {"deployments": len(runs),
                   "success_rate": round(success_rate * 100, 1) if success_rate is not None else None,
                   "rollback_rate": round((rollback_rate or 0) * 100, 1) if rollback_rate is not None else None,
                   "change_failure_predictions": len(preds)}
        detail = (f"{len(runs)} deployment(s), "
                  + (f"{round(success_rate*100)}% success, " if success_rate is not None else "")
                  + f"{len(preds)} change-failure prediction(s).") if (runs or preds) else \
                 "No deployments tracked yet."
        return _Cat(MaturityCategory.DEPLOYMENT.value, score, detail, signals)

    async def _score_slo(self, organization_id) -> _Cat:
        services = await self.service_repo.list_for_org(organization_id)
        if not services:
            return _Cat(MaturityCategory.SLO.value, 0, "No services catalogued; no SLOs defined.",
                        {"services": 0, "services_with_slo": 0})
        with_slo = 0
        with_budget = 0
        healthy_burn = 0
        for svc in services:
            slos = await self.slo_repo.list_for_service(svc.id, organization_id)
            if slos:
                with_slo += 1
            rep = await self.health._compute(organization_id, svc, slos, full=False)
            if rep.error_budget and rep.error_budget.remaining_percentage is not None:
                with_budget += 1
            if rep.burn_rate and rep.burn_rate.status == "NORMAL":
                healthy_burn += 1
        n = len(services)
        coverage = with_slo / n
        score = coverage * 50
        score += 25 if with_budget else 0
        score += (healthy_burn / n) * 25
        signals = {"services": n, "services_with_slo": with_slo,
                   "services_with_error_budget": with_budget, "healthy_burn": healthy_burn}
        detail = f"{with_slo}/{n} service(s) have SLOs; {with_budget} track error budgets."
        return _Cat(MaturityCategory.SLO.value, score, detail, signals)

    async def _score_capacity(self, organization_id) -> _Cat:
        forecasts = await self.forecast_repo.list_recent(organization_id, limit=500)
        metrics = await self.metric_repo.query(organization_id)
        score = 0
        score += 40 if metrics else 0
        score += 40 if forecasts else 0
        if forecasts:
            healthy = sum(1 for f in forecasts if (f.status or "HEALTHY") == "HEALTHY")
            score += (healthy / len(forecasts)) * 20
        signals = {"capacity_metrics": len(metrics), "forecasts": len(forecasts)}
        detail = (f"{len(metrics)} metric sample(s), {len(forecasts)} forecast(s)."
                  if (metrics or forecasts) else "No capacity metrics or forecasts yet.")
        return _Cat(MaturityCategory.CAPACITY.value, score, detail, signals)

    async def _score_cost(self, organization_id) -> _Cat:
        latest = await self.cost_repo.latest(organization_id)
        _, total = await self.cost_repo.list_for_org(organization_id, offset=0, limit=1)
        score = 0
        if latest:
            score += 50
            score += 25 if (latest.potential_savings or 0) > 0 else 0
            score += (latest.optimization_score or 0) * 0.25
        signals = {"analyses": total,
                   "optimization_score": latest.optimization_score if latest else None,
                   "potential_savings": round(latest.potential_savings, 2) if latest else None}
        detail = (f"{total} analysis(es); optimization score {latest.optimization_score}/100."
                  if latest else "No cost optimization analysis has been run.")
        return _Cat(MaturityCategory.COST_OPTIMIZATION.value, score, detail, signals)

    async def _score_oncall(self, organization_id) -> _Cat:
        owners = await self.owner_repo.list_for_org(organization_id)
        schedules = await self.schedule_repo.list_for_org(organization_id)
        policies = await self.escalation_repo.list_for_org(organization_id)
        assignments = await self.assignment_repo.list_for_org(organization_id, limit=1)
        score = 0
        score += 30 if owners else 0
        score += 30 if schedules else 0
        score += 25 if policies else 0
        score += 15 if assignments else 0
        signals = {"service_owners": len(owners), "oncall_schedules": len(schedules),
                   "escalation_policies": len(policies), "has_assignments": bool(assignments)}
        detail = (f"{len(owners)} owner(s), {len(schedules)} schedule(s), {len(policies)} escalation policy(ies)."
                  if (owners or schedules or policies) else "No on-call ownership or escalation configured.")
        return _Cat(MaturityCategory.ONCALL.value, score, detail, signals)

    # ------------------------------------------------- strengths/weaknesses
    @staticmethod
    def _strengths_weaknesses(cats: list[_Cat]):
        strengths = [
            f"{_CATEGORY_LABEL[c.category]} is {_level(c.score).lower()} ({c.score}/100)."
            for c in sorted(cats, key=lambda x: x.score, reverse=True)
            if c.score >= 60
        ]
        weaknesses = [
            f"{_CATEGORY_LABEL[c.category]} is {_level(c.score).lower()} ({c.score}/100)."
            for c in sorted(cats, key=lambda x: x.score)
            if c.score < 40
        ]
        return strengths, weaknesses

    @staticmethod
    def _recommendations(cats: list[_Cat]) -> list[Recommendation]:
        recs = []
        for c in cats:
            if c.score >= 80:
                continue
            impact = round(_WEIGHTS[c.category] * (100 - c.score), 1)
            priority = "HIGH" if impact >= 8 else ("MEDIUM" if impact >= 4 else "LOW")
            recs.append(Recommendation(
                category=c.category, priority=priority,
                recommendation=_ADVICE[c.category], impact=impact,
            ))
        recs.sort(key=lambda r: r.impact, reverse=True)
        return recs

    @staticmethod
    def _summary(overall, level, cats, prev_overall) -> str:
        best = max(cats, key=lambda c: c.score)
        worst = min(cats, key=lambda c: c.score)
        trend = ""
        if prev_overall is not None:
            delta = overall - prev_overall
            if delta > 0:
                trend = f" Up {delta} point(s) since the last assessment."
            elif delta < 0:
                trend = f" Down {abs(delta)} point(s) since the last assessment."
            else:
                trend = " Unchanged since the last assessment."
        return (f"Overall reliability maturity is {overall}/100 ({level}). "
                f"Strongest area: {_CATEGORY_LABEL[best.category]} ({best.score}); "
                f"weakest area: {_CATEGORY_LABEL[worst.category]} ({worst.score})." + trend)

    # ------------------------------------------------------------- shaping
    async def _to_response(self, assessment, *, cats=None, category_rows=None, recs=None) -> AssessmentResponse:
        if category_rows is not None:
            categories = [
                CategoryScore(category=r.category, score=r.score, maturity_level=r.maturity_level,
                              weight=r.weight, detail=r.detail or "", signals=r.signals or {})
                for r in category_rows
            ]
        else:
            categories = [
                CategoryScore(category=c.category, score=c.score, maturity_level=_level(c.score),
                              weight=_WEIGHTS[c.category], detail=c.detail, signals=c.signals)
                for c in (cats or [])
            ]
            categories.sort(key=lambda c: c.weight, reverse=True)
        if recs is not None:
            rec_objs = recs
        else:
            rec_objs = [Recommendation(**r) for r in (assessment.recommendations or [])]
        return AssessmentResponse(
            id=assessment.id,
            organization_id=assessment.organization_id,
            overall_score=assessment.overall_score,
            maturity_level=assessment.maturity_level,
            summary=assessment.summary,
            strengths=assessment.strengths or [],
            weaknesses=assessment.weaknesses or [],
            recommendations=rec_objs,
            categories=categories,
            details=assessment.details or {},
            created_at=assessment.created_at,
        )
