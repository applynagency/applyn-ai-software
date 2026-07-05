"""Sprint 43B — Cost Optimization Intelligence engine.

Read-only and rules-based. Mines persisted capacity utilization samples (43A)
plus scope metadata to surface where money is being wasted and how much could be
saved. It never scales, deletes, or modifies infrastructure — every output is a
recommendation.

What it computes
----------------
* Current monthly cost      = sum(latest_capacity × unit_cost) over scoped groups
* Idle detection            = mean utilization < IDLE_THRESHOLD  → full cost is waste
* Over-provisioning         = mean utilization < OVER_THRESHOLD[type]  → rightsize
* Rightsizing target        = peak_usage / target_utilization → recommended capacity
* Estimated waste           = idle full cost + over-provisioned excess cost
* Non-prod scheduling        = night+weekend shutdown on dev/test/staging (~65% off)
* Potential savings         = estimated_waste + non-prod scheduling savings
* Optimization score (0-100) = 100 × (1 − estimated_waste / current_cost)
* Cost forecast (30/90/365) = projected usage growth → required capacity × unit_cost
* Cost trend                = weekly / monthly usage-driven effective cost + anomalies

Formulas are deterministic. No model training. Org-scoped and audited.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NexoraException
from app.models.cost_optimization import CostRecommendationKind, OptimizationLevel
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.capacity import CapacityMetricRepository
from app.repositories.cost_optimization import CostOptimizationRepository
from app.schemas.cost_optimization import (
    CostAnalysisListResponse,
    CostAnalysisSummary,
    CostDashboard,
    CostRecommendation,
    CostReport,
    CostTrendPoint,
    NameCost,
)
from app.services.capacity import _UNIT_COST  # shared deterministic unit-cost model
from app.tenancy.permissions import can_read_ai_teams

logger = structlog.get_logger(__name__)

# Target utilization fraction used for rightsizing & forecasting (headroom-aware).
_TARGET_UTIL = {
    "CPU": 0.60, "MEMORY": 0.70, "STORAGE": 0.75, "NETWORK": 0.60,
    "NODE": 0.65, "POD": 0.70, "VM": 0.60, "LOAD_BALANCER": 0.50, "DATABASE": 0.65,
}
_DEFAULT_TARGET = 0.65

# A resource whose mean utilization is below this is treated as idle/unused.
_IDLE_THRESHOLD = 5.0

# Below this mean utilization a still-used resource is over-provisioned.
_OVER_THRESHOLD = {"CPU": 20.0, "MEMORY": 30.0}
_DEFAULT_OVER = 25.0

# Non-production environments are candidates for shutdown scheduling.
_NONPROD_ENVS = {"dev", "development", "test", "testing", "qa", "staging", "stage", "sandbox", "uat"}
# Night (weekday off-hours) + weekend shutdown ≈ 65% of hours reclaimable.
_NONPROD_SAVINGS_FRACTION = 0.65

_IDLE_LABEL = {
    "NODE": "Idle Kubernetes node",
    "POD": "Idle pod allocation",
    "STORAGE": "Unused storage volume",
    "NETWORK": "Idle load balancer / network",
    "LOAD_BALANCER": "Unused load balancer",
    "DATABASE": "Underutilized database",
    "VM": "Idle VM instance",
    "CPU": "Idle CPU allocation",
    "MEMORY": "Idle memory allocation",
}


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _linfit(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Ordinary least squares → (slope, intercept)."""
    n = len(xs)
    if n == 0:
        return 0.0, 0.0
    if n == 1:
        return 0.0, ys[0]
    mx = sum(xs) / n
    my = sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return 0.0, my
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / denom
    return slope, my - slope * mx


class _Group:
    """Per-scope/resource aggregation used by the analyzer."""

    __slots__ = ("cluster", "service", "environment", "resource_type", "unit",
                 "capacity", "samples")

    def __init__(self, cluster, service, environment, resource_type):
        self.cluster = cluster
        self.service = service
        self.environment = environment
        self.resource_type = resource_type
        self.unit = None
        self.capacity = 0.0
        self.samples: list[tuple[datetime, float, float]] = []  # (ts, usage, capacity)

    @property
    def scope_label(self) -> str:
        return (
            f"{self.service or '*'} / {self.environment or '*'} / "
            f"{self.cluster or '*'} · {self.resource_type}"
        )

    @property
    def peak_usage(self) -> float:
        return max((u for _, u, _ in self.samples), default=0.0)

    @property
    def mean_util(self) -> float:
        utils = [u / c * 100.0 for _, u, c in self.samples if c > 0]
        return sum(utils) / len(utils) if utils else 0.0

    @property
    def unit_cost(self) -> float:
        return _UNIT_COST.get(self.resource_type, 0.0)

    @property
    def current_cost(self) -> float:
        return self.capacity * self.unit_cost

    @property
    def is_nonprod(self) -> bool:
        return (self.environment or "").strip().lower() in _NONPROD_ENVS


class CostOptimizationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.metric_repo = CapacityMetricRepository(session)
        self.repo = CostOptimizationRepository(session)
        self.audit_repo = AuditLogRepository(session)

    def _ensure_read(self, user: User, org_context: OrgContext) -> None:
        if not user.is_superuser and (
            not org_context.role or not can_read_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    # ------------------------------------------------------------------ analyze
    async def analyze(self, user: User, org_context: OrgContext, req) -> CostReport:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        since = _now() - timedelta(days=req.lookback_days)

        metrics = await self.metric_repo.query(
            organization_id,
            cluster=req.cluster,
            service=req.service,
            environment=req.environment,
            since=since,
        )
        if not metrics:
            raise NexoraException(
                "No capacity metrics found for the requested scope.", status_code=400
            )

        groups = self._group(metrics)
        result = self._compute(groups)

        row = await self.repo.create(
            organization_id=organization_id,
            cluster=req.cluster,
            service=req.service,
            environment=req.environment,
            current_cost=result["current_cost"],
            estimated_waste=result["estimated_waste"],
            potential_savings=result["potential_savings"],
            optimized_cost=result["optimized_cost"],
            annual_savings=result["annual_savings"],
            savings_percentage=result["savings_percentage"],
            optimization_score=result["optimization_score"],
            optimization_level=result["optimization_level"],
            forecast_30d=result["forecast_30d"],
            forecast_90d=result["forecast_90d"],
            forecast_365d=result["forecast_365d"],
            idle_count=result["idle_count"],
            overprovisioned_count=result["overprovisioned_count"],
            nonprod_count=result["nonprod_count"],
            confidence=result["confidence"],
            details=result["details"],
            created_by=user.id,
        )
        await self.audit_repo.log(
            action="cost_analysis_created",
            resource_type="cost_optimization_analysis",
            resource_id=row.id,
            user_id=user.id,
            details={
                "organization_id": organization_id,
                "current_cost": result["current_cost"],
                "potential_savings": result["potential_savings"],
                "optimization_score": result["optimization_score"],
            },
        )
        await self.session.commit()
        return self._to_report(row)

    # -------------------------------------------------------------- aggregation
    @staticmethod
    def _group(metrics) -> list[_Group]:
        buckets: dict[tuple, _Group] = {}
        for m in metrics:
            key = (m.cluster, m.service, m.environment, m.resource_type)
            g = buckets.get(key)
            if g is None:
                g = _Group(m.cluster, m.service, m.environment, m.resource_type)
                buckets[key] = g
            ts = _aware(m.recorded_at) or _now()
            g.samples.append((ts, m.usage, m.capacity or 0.0))
            if m.unit and not g.unit:
                g.unit = m.unit
        # latest capacity per group (samples sorted asc by recorded_at from repo).
        for g in buckets.values():
            g.samples.sort(key=lambda s: s[0])
            if g.samples:
                g.capacity = g.samples[-1][2]
        return list(buckets.values())

    # ----------------------------------------------------------------- compute
    def _compute(self, groups: list[_Group]) -> dict:
        now = _now()
        current_cost = 0.0
        estimated_waste = 0.0
        nonprod_schedule_savings = 0.0
        recommendations: list[dict] = []
        idle_count = overprovisioned_count = nonprod_count = 0
        total_samples = 0

        cost_by_service: dict[str, float] = defaultdict(float)
        cost_by_environment: dict[str, float] = defaultdict(float)

        f30 = f90 = f365 = 0.0

        for g in groups:
            total_samples += len(g.samples)
            gcost = g.current_cost
            current_cost += gcost
            cost_by_service[g.service or "unassigned"] += gcost
            cost_by_environment[g.environment or "unassigned"] += gcost

            target = _TARGET_UTIL.get(g.resource_type, _DEFAULT_TARGET)
            mean_util = g.mean_util
            remaining_cost = gcost  # cost that would still run after rightsizing

            over_threshold = _OVER_THRESHOLD.get(g.resource_type, _DEFAULT_OVER)

            if g.unit_cost > 0 and gcost > 0 and mean_util < _IDLE_THRESHOLD:
                # Idle / unused — the entire spend is waste.
                idle_count += 1
                estimated_waste += gcost
                remaining_cost = 0.0
                label = _IDLE_LABEL.get(g.resource_type, "Idle resource")
                recommendations.append({
                    "kind": CostRecommendationKind.IDLE_RESOURCE.value,
                    "resource_type": g.resource_type,
                    "scope": g.scope_label,
                    "title": f"{label} ({round(mean_util, 1)}% utilized)",
                    "detail": (
                        f"{label} averaging {round(mean_util, 1)}% utilization over the "
                        f"window. Consider decommissioning or consolidating."
                    ),
                    "current_cost": round(gcost, 2),
                    "projected_cost": 0.0,
                    "monthly_savings": round(gcost, 2),
                    "action": "Decommission or consolidate this resource (advisory).",
                })
            elif g.unit_cost > 0 and gcost > 0 and mean_util < over_threshold:
                # Over-provisioned — rightsize down to a headroom-aware target.
                overprovisioned_count += 1
                recommended_cap = max(g.peak_usage / target, 0.0) if target > 0 else g.capacity
                recommended_cap = min(recommended_cap, g.capacity)
                recommended_cost = recommended_cap * g.unit_cost
                savings = max(0.0, gcost - recommended_cost)
                estimated_waste += savings
                remaining_cost = recommended_cost
                recommendations.append({
                    "kind": CostRecommendationKind.OVERPROVISIONED.value,
                    "resource_type": g.resource_type,
                    "scope": g.scope_label,
                    "title": f"Over-provisioned {g.resource_type} ({round(mean_util, 1)}% utilized)",
                    "detail": (
                        f"Mean utilization {round(mean_util, 1)}% with peak "
                        f"{round(g.peak_usage, 2)} {g.unit or ''}. Rightsize capacity "
                        f"from {round(g.capacity, 2)} to ~{round(recommended_cap, 2)}."
                    ),
                    "current_cost": round(gcost, 2),
                    "projected_cost": round(recommended_cost, 2),
                    "monthly_savings": round(savings, 2),
                    "action": self._rightsize_action(g.resource_type),
                })

            # Non-production scheduling on whatever still runs.
            if g.is_nonprod and remaining_cost > 0:
                sched = remaining_cost * _NONPROD_SAVINGS_FRACTION
                if sched > 0:
                    nonprod_count += 1
                    nonprod_schedule_savings += sched
                    recommendations.append({
                        "kind": CostRecommendationKind.NON_PROD_SCHEDULE.value,
                        "resource_type": g.resource_type,
                        "scope": g.scope_label,
                        "title": f"Schedule shutdown for non-prod {g.resource_type}",
                        "detail": (
                            f"'{g.environment}' is non-production. Apply night and weekend "
                            f"shutdown schedules to reclaim ~{int(_NONPROD_SAVINGS_FRACTION * 100)}% "
                            f"of idle hours."
                        ),
                        "current_cost": round(remaining_cost, 2),
                        "projected_cost": round(remaining_cost - sched, 2),
                        "monthly_savings": round(sched, 2),
                        "action": "Apply night/weekend shutdown schedule (advisory).",
                    })

            # Forecast contribution for this group.
            c30, c90, c365 = self._forecast_group(g, now, target)
            f30 += c30
            f90 += c90
            f365 += c365

        potential_savings = estimated_waste + nonprod_schedule_savings
        potential_savings = min(potential_savings, current_cost)
        optimized_cost = max(0.0, current_cost - potential_savings)
        annual_savings = potential_savings * 12.0
        savings_pct = (potential_savings / current_cost * 100.0) if current_cost > 0 else 0.0

        waste_pct = (estimated_waste / current_cost) if current_cost > 0 else 0.0
        score = int(round(max(0.0, min(100.0, 100.0 * (1.0 - waste_pct)))))
        level = self._level(score)

        recommendations.sort(key=lambda r: r["monthly_savings"], reverse=True)

        weekly = self._trend(groups, now, bucket="week", periods=8)
        monthly = self._trend(groups, now, bucket="month", periods=6)

        by_service = sorted(
            ({"name": k, "cost": round(v, 2)} for k, v in cost_by_service.items()),
            key=lambda x: x["cost"], reverse=True,
        )
        by_env = sorted(
            ({"name": k, "cost": round(v, 2)} for k, v in cost_by_environment.items()),
            key=lambda x: x["cost"], reverse=True,
        )

        return {
            "current_cost": round(current_cost, 2),
            "estimated_waste": round(estimated_waste, 2),
            "potential_savings": round(potential_savings, 2),
            "optimized_cost": round(optimized_cost, 2),
            "annual_savings": round(annual_savings, 2),
            "savings_percentage": round(savings_pct, 2),
            "optimization_score": score,
            "optimization_level": level,
            "forecast_30d": round(f30, 2),
            "forecast_90d": round(f90, 2),
            "forecast_365d": round(f365, 2),
            "idle_count": idle_count,
            "overprovisioned_count": overprovisioned_count,
            "nonprod_count": nonprod_count,
            "confidence": self._confidence(total_samples),
            "details": {
                "recommendations": recommendations,
                "weekly_trend": weekly,
                "monthly_trend": monthly,
                "cost_by_service": by_service,
                "cost_by_environment": by_env,
            },
        }

    @staticmethod
    def _rightsize_action(rt: str) -> str:
        return {
            "CPU": "Lower CPU requests / use smaller node pool (advisory).",
            "MEMORY": "Lower memory limits (advisory).",
            "POD": "Reduce replica count (advisory).",
            "NODE": "Use a smaller node pool (advisory).",
            "VM": "Move to a smaller VM size (advisory).",
            "STORAGE": "Shrink or tier storage (advisory).",
            "DATABASE": "Downsize database instance (advisory).",
        }.get(rt, "Rightsize this resource (advisory).")

    def _forecast_group(self, g: _Group, now: datetime, target: float) -> tuple[float, float, float]:
        """Project usage growth → required capacity × unit_cost at 30/90/365 days."""
        if g.unit_cost <= 0 or not g.samples:
            return g.current_cost, g.current_cost, g.current_cost
        xs = [(ts - now).total_seconds() / 86400.0 for ts, _, _ in g.samples]
        ys = [u for _, u, _ in g.samples]
        slope, intercept = _linfit(xs, ys)
        latest_usage = g.samples[-1][1]
        base = max(latest_usage, intercept) if intercept > 0 else latest_usage

        def cost_at(h: float) -> float:
            proj_usage = max(0.0, base + slope * h)
            needed = (proj_usage / target) if target > 0 else g.capacity
            cap = max(g.capacity, needed)
            return cap * g.unit_cost

        return cost_at(30), cost_at(90), cost_at(365)

    def _trend(self, groups: list[_Group], now: datetime, *, bucket: str, periods: int) -> list[dict]:
        """Usage-driven effective cost per period (cost to serve the observed load)."""
        def key(ts: datetime) -> str:
            if bucket == "week":
                iso = ts.isocalendar()
                return f"{iso[0]}-W{iso[1]:02d}"
            return f"{ts.year}-{ts.month:02d}"

        # accumulate per-period: sum of (mean usage in period / target * unit_cost) per group
        per_period_group: dict[str, dict[tuple, list[float]]] = defaultdict(lambda: defaultdict(list))
        targets: dict[tuple, tuple[float, float]] = {}
        for g in groups:
            if g.unit_cost <= 0:
                continue
            gkey = (g.cluster, g.service, g.environment, g.resource_type)
            targets[gkey] = (_TARGET_UTIL.get(g.resource_type, _DEFAULT_TARGET), g.unit_cost)
            for ts, usage, _ in g.samples:
                per_period_group[key(ts)][gkey].append(usage)

        period_cost: dict[str, float] = {}
        for pk, gmap in per_period_group.items():
            total = 0.0
            for gkey, usages in gmap.items():
                target, unit_cost = targets[gkey]
                mean_usage = sum(usages) / len(usages)
                total += (mean_usage / target if target > 0 else 0.0) * unit_cost
            period_cost[pk] = round(total, 2)

        ordered = sorted(period_cost.items())[-periods:]
        out = []
        prev = None
        for pk, cost in ordered:
            anomaly = prev is not None and prev > 0 and cost > prev * 1.25
            out.append({"period": pk, "cost": cost, "anomaly": bool(anomaly)})
            prev = cost
        return out

    @staticmethod
    def _level(score: int) -> str:
        if score >= 85:
            return OptimizationLevel.EXCELLENT.value
        if score >= 70:
            return OptimizationLevel.GOOD.value
        if score >= 40:
            return OptimizationLevel.NEEDS_IMPROVEMENT.value
        return OptimizationLevel.CRITICAL_WASTE.value

    @staticmethod
    def _confidence(n: int) -> float:
        if n >= 60:
            return 0.9
        if n >= 20:
            return 0.75
        if n >= 8:
            return 0.6
        if n >= 3:
            return 0.45
        return 0.3

    # --------------------------------------------------------------- retrieval
    async def list_analyses(self, user, org_context, *, offset: int, limit: int) -> CostAnalysisListResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        rows, total = await self.repo.list_for_org(organization_id, offset=offset, limit=limit)
        return CostAnalysisListResponse(
            items=[CostAnalysisSummary.model_validate(r) for r in rows],
            total=total,
            offset=offset,
            limit=limit,
        )

    async def get_analysis(self, user, org_context, analysis_id: str) -> CostReport:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        row = await self.repo.get_for_org(analysis_id, organization_id)
        if row is None:
            raise NexoraException("Cost analysis not found.", status_code=404)
        await self.audit_repo.log(
            action="cost_analysis_viewed",
            resource_type="cost_optimization_analysis",
            resource_id=analysis_id,
            user_id=user.id,
            details={"organization_id": organization_id},
        )
        await self.session.commit()
        return self._to_report(row)

    async def dashboard(self, user, org_context) -> CostDashboard:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        row = await self.repo.latest(organization_id)
        await self.audit_repo.log(
            action="cost_dashboard_viewed",
            resource_type="cost_optimization_analysis",
            resource_id=organization_id,
            user_id=user.id,
            details={"organization_id": organization_id, "has_data": row is not None},
        )
        await self.session.commit()

        if row is None:
            return CostDashboard(has_data=False)

        report = self._to_report(row)
        return CostDashboard(
            has_data=True,
            current_cost=report.current_cost,
            forecast_30d=report.forecast_30d,
            forecast_90d=report.forecast_90d,
            forecast_365d=report.forecast_365d,
            estimated_waste=report.estimated_waste,
            potential_savings=report.potential_savings,
            annual_savings=report.annual_savings,
            optimized_cost=report.optimized_cost,
            savings_percentage=report.savings_percentage,
            optimization_score=report.optimization_score,
            optimization_level=report.optimization_level,
            idle_count=report.idle_count,
            overprovisioned_count=report.overprovisioned_count,
            nonprod_count=report.nonprod_count,
            analyzed_at=report.created_at,
            top_recommendations=report.recommendations[:8],
            weekly_trend=report.weekly_trend,
            cost_by_service=report.cost_by_service,
            cost_by_environment=report.cost_by_environment,
        )

    @staticmethod
    def _to_report(row) -> CostReport:
        details = row.details if isinstance(row.details, dict) else {}
        return CostReport(
            id=row.id,
            organization_id=row.organization_id,
            cluster=row.cluster,
            service=row.service,
            environment=row.environment,
            current_cost=row.current_cost,
            estimated_waste=row.estimated_waste,
            potential_savings=row.potential_savings,
            optimized_cost=row.optimized_cost,
            annual_savings=row.annual_savings,
            savings_percentage=row.savings_percentage,
            optimization_score=row.optimization_score,
            optimization_level=row.optimization_level,
            forecast_30d=row.forecast_30d,
            forecast_90d=row.forecast_90d,
            forecast_365d=row.forecast_365d,
            idle_count=row.idle_count,
            overprovisioned_count=row.overprovisioned_count,
            nonprod_count=row.nonprod_count,
            confidence=row.confidence,
            created_at=row.created_at,
            recommendations=[CostRecommendation(**r) for r in details.get("recommendations", [])],
            weekly_trend=[CostTrendPoint(**t) for t in details.get("weekly_trend", [])],
            monthly_trend=[CostTrendPoint(**t) for t in details.get("monthly_trend", [])],
            cost_by_service=[NameCost(**c) for c in details.get("cost_by_service", [])],
            cost_by_environment=[NameCost(**c) for c in details.get("cost_by_environment", [])],
        )
