"""Sprint 43A — Capacity Planning & Forecasting engine.

Read-only and rules-based. From persisted utilization samples it computes a
least-squares growth trend, projects 7/30/90-day utilization, predicts
saturation (crossing the threshold) and exhaustion (reaching 100%), emits an
advisory scaling recommendation, and estimates cost impact.

Formulas
--------
utilization%        = usage / capacity * 100
linear fit          = least squares of utilization% vs days-from-now (x≤0 past)
current_utilization = intercept (fit value at now)
growth_rate_per_day = slope (%/day)
forecast(h days)    = current + slope × h
saturation_date     = now + (threshold − current) / slope   (slope > 0)
exhaustion_date     = now + (100 − current) / slope          (slope > 0)
needed_capacity     = capacity × forecast_30d / threshold
projected_cost      = max(capacity, needed_capacity) × unit_cost

It never scales, provisions, or mutates infrastructure.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NexoraException
from app.models.capacity import (
    CapacityStatus,
    CapacityTrend,
    ResourceType,
    ScalingAction,
)
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.capacity import CapacityForecastRepository, CapacityMetricRepository
from app.schemas.capacity import (
    CapacityDashboard,
    ForecastResponse,
    ResourceSummary,
    TrendPoint,
)
from app.tenancy.permissions import can_read_ai_teams, can_write_ai_teams

logger = structlog.get_logger(__name__)

# Monthly unit cost per resource capacity unit (USD). Deterministic cost model.
_UNIT_COST = {
    "CPU": 30.0,            # per vCPU
    "MEMORY": 5.0,          # per GB
    "STORAGE": 0.10,        # per GB
    "NETWORK": 20.0,        # per Gbps
    "NODE": 200.0,          # per node
    "POD": 10.0,            # per pod slot
    "VM": 120.0,            # per VM instance
    "LOAD_BALANCER": 25.0,  # per load balancer
    "DATABASE": 150.0,      # per database instance
}

# Resource → advisory scaling action.
_ACTION = {
    "CPU": ScalingAction.SCALE_CLUSTER.value,
    "MEMORY": ScalingAction.INCREASE_MEMORY.value,
    "STORAGE": ScalingAction.INCREASE_STORAGE.value,
    "NETWORK": ScalingAction.SCALE_CLUSTER.value,
    "NODE": ScalingAction.ADD_NODES.value,
    "POD": ScalingAction.INCREASE_REPLICAS.value,
}

_ACTION_TEXT = {
    ScalingAction.ADD_NODES.value: "Add nodes to the cluster",
    ScalingAction.INCREASE_MEMORY.value: "Increase memory allocation",
    ScalingAction.INCREASE_STORAGE.value: "Increase storage capacity",
    ScalingAction.INCREASE_REPLICAS.value: "Increase replica count",
    ScalingAction.SCALE_CLUSTER.value: "Scale out the cluster",
    ScalingAction.NONE.value: "No action required",
}


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _linfit(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Ordinary least squares → (slope, intercept). Falls back to a flat line at
    the mean when the points are degenerate (n<2 or zero x-variance)."""
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
    intercept = my - slope * mx
    return slope, intercept


class CapacityForecaster:
    """Pure, deterministic projector over a resource's samples."""

    def forecast(self, samples: list, threshold: float) -> dict:
        now = _now()
        pts = []
        for s in samples:
            cap = s.capacity or 0.0
            if cap <= 0:
                continue
            ts = _aware(s.recorded_at) or now
            util = max(0.0, s.usage / cap * 100.0)
            x_days = (ts - now).total_seconds() / 86400.0
            pts.append((x_days, util, ts, s.usage, cap, s.unit))
        pts.sort(key=lambda p: p[0])

        data_points = len(pts)
        if data_points == 0:
            return {
                "current_utilization": 0.0, "slope": 0.0, "f7": 0.0, "f30": 0.0, "f90": 0.0,
                "saturation_date": None, "exhaustion_date": None, "trend": CapacityTrend.STABLE.value,
                "data_points": 0, "capacity": 0.0, "usage": 0.0, "unit": None, "trend_points": [],
            }

        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        slope, intercept = _linfit(xs, ys)
        latest = pts[-1]
        # current = regression value at now, but never below the latest observed.
        current = max(0.0, intercept)
        if abs(intercept) < 1e-9 and slope == 0.0:
            current = latest[1]

        def proj(h: float) -> float:
            return max(0.0, current + slope * h)

        f7, f30, f90 = proj(7), proj(30), proj(90)

        sat_date = exh_date = None
        if slope > 1e-6:
            if current < threshold:
                t = (threshold - current) / slope
                if 0 < t <= 3650:
                    sat_date = now + timedelta(days=t)
            if current < 100:
                t = (100 - current) / slope
                if 0 < t <= 3650:
                    exh_date = now + timedelta(days=t)

        if slope > 0.05:
            trend = CapacityTrend.GROWING.value
        elif slope < -0.05:
            trend = CapacityTrend.DECLINING.value
        else:
            trend = CapacityTrend.STABLE.value

        trend_points = [{"timestamp": p[2], "utilization": round(p[1], 2)} for p in pts[-60:]]

        return {
            "current_utilization": round(current, 2),
            "slope": round(slope, 4),
            "f7": round(f7, 2), "f30": round(f30, 2), "f90": round(f90, 2),
            "saturation_date": sat_date, "exhaustion_date": exh_date, "trend": trend,
            "data_points": data_points, "capacity": latest[4], "usage": latest[3],
            "unit": latest[5], "trend_points": trend_points,
        }


class CapacityService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.metric_repo = CapacityMetricRepository(session)
        self.forecast_repo = CapacityForecastRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.forecaster = CapacityForecaster()

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

    # --------------------------------------------------------------- collection
    async def ingest(self, user, org_context, samples) -> int:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        now = _now()
        rows = []
        for s in samples:
            rt = s.resource_type.upper()
            if rt not in {r.value for r in ResourceType}:
                raise NexoraException(f"Invalid resource_type: {s.resource_type}", status_code=400)
            rows.append(dict(
                organization_id=organization_id,
                cluster=s.cluster,
                service=s.service,
                environment=s.environment,
                resource_type=rt,
                usage=s.usage,
                capacity=s.capacity,
                unit=s.unit,
                recorded_at=_aware(s.recorded_at) or now,
            ))
        n = await self.metric_repo.add_many(rows)
        await self.audit_repo.log(
            action="capacity_metrics_ingested",
            resource_type="capacity_metric",
            resource_id=organization_id,
            user_id=user.id,
            details={"organization_id": organization_id, "ingested": n},
        )
        await self.session.commit()
        return n

    # ---------------------------------------------------------------- forecasts
    async def create_forecast(self, user, org_context, req) -> list[ForecastResponse]:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        since = _now() - timedelta(days=req.lookback_days)

        if req.resource_type:
            resource_types = [req.resource_type.upper()]
        else:
            resource_types = await self.metric_repo.distinct_resource_types(
                organization_id, cluster=req.cluster, service=req.service, environment=req.environment
            )
        if not resource_types:
            raise NexoraException("No capacity metrics found for the requested scope.", status_code=400)

        created: list[ForecastResponse] = []
        for rt in resource_types:
            samples = await self.metric_repo.query(
                organization_id, resource_type=rt, cluster=req.cluster,
                service=req.service, environment=req.environment, since=since,
            )
            if not samples:
                if req.resource_type:
                    raise NexoraException(
                        f"No capacity metrics found for resource {rt} in scope.", status_code=400
                    )
                continue
            row = await self._build_forecast(organization_id, user.id, rt, req, samples)
            created.append(self._to_response(row))

        if not created:
            raise NexoraException("No capacity metrics found for the requested scope.", status_code=400)

        await self.audit_repo.log(
            action="forecast_created",
            resource_type="capacity_forecast",
            resource_id=created[0].id,
            user_id=user.id,
            details={
                "organization_id": organization_id,
                "resources": [c.resource_type for c in created],
                "count": len(created),
            },
        )
        await self.session.commit()
        return created

    async def _build_forecast(self, organization_id, user_id, rt, req, samples):
        f = self.forecaster.forecast(samples, req.saturation_threshold)
        status, action, rec_text = self._classify(rt, f, req.saturation_threshold)
        current_cost, projected_cost, delta = self._cost(rt, f, req.saturation_threshold)
        confidence = self._confidence(f["data_points"])

        row = await self.forecast_repo.create(
            organization_id=organization_id,
            cluster=req.cluster,
            service=req.service,
            environment=req.environment,
            resource_type=rt,
            unit=f["unit"],
            current_usage=round(f["usage"], 4),
            capacity=round(f["capacity"], 4),
            current_utilization=f["current_utilization"],
            growth_rate_per_day=f["slope"],
            trend=f["trend"],
            forecast_7d=f["f7"],
            forecast_30d=f["f30"],
            forecast_90d=f["f90"],
            saturation_threshold=req.saturation_threshold,
            saturation_date=f["saturation_date"],
            exhaustion_date=f["exhaustion_date"],
            status=status,
            recommendation_action=action,
            recommendation=rec_text,
            current_cost=current_cost,
            projected_cost=projected_cost,
            delta_cost=delta,
            confidence=confidence,
            data_points=f["data_points"],
            details={"trend_points": [
                {"timestamp": p["timestamp"].isoformat(), "utilization": p["utilization"]}
                for p in f["trend_points"]
            ]},
            created_by=user_id,
        )
        return row

    def _classify(self, rt, f, threshold) -> tuple[str, str, str]:
        now = _now()
        exh = f["exhaustion_date"]
        sat = f["saturation_date"]
        f30 = f["f30"]
        critical = f30 >= 100 or (exh is not None and exh <= now + timedelta(days=30))
        warning = f30 >= threshold or (sat is not None and sat <= now + timedelta(days=90))
        if critical:
            status = CapacityStatus.CRITICAL.value
        elif warning:
            status = CapacityStatus.WARNING.value
        else:
            status = CapacityStatus.HEALTHY.value

        if status == CapacityStatus.HEALTHY.value:
            return status, ScalingAction.NONE.value, _ACTION_TEXT[ScalingAction.NONE.value]

        action = _ACTION.get(rt, ScalingAction.SCALE_CLUSTER.value)
        when = ""
        if exh is not None:
            days = max(0, (exh - now).days)
            when = f" Projected to reach 100% in ~{days} day(s)."
        elif sat is not None:
            days = max(0, (sat - now).days)
            when = f" Projected to reach {round(threshold)}% in ~{days} day(s)."
        rec = f"{_ACTION_TEXT[action]} for {rt.lower()}.{when}"
        return status, action, rec

    def _cost(self, rt, f, threshold) -> tuple[float, float, float]:
        unit_cost = _UNIT_COST.get(rt, 0.0)
        capacity = f["capacity"]
        current_cost = capacity * unit_cost
        # Capacity required to keep the 30-day projection under the threshold.
        needed = capacity * (f["f30"] / threshold) if threshold > 0 else capacity
        projected_capacity = max(capacity, needed)
        projected_cost = projected_capacity * unit_cost
        return round(current_cost, 2), round(projected_cost, 2), round(projected_cost - current_cost, 2)

    @staticmethod
    def _confidence(n: int) -> float:
        if n >= 30:
            return 0.9
        if n >= 10:
            return 0.75
        if n >= 4:
            return 0.6
        if n >= 2:
            return 0.45
        return 0.3

    async def list_forecasts(self, user, org_context, *, offset: int, limit: int):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        rows, total = await self.forecast_repo.list_for_org(organization_id, offset=offset, limit=limit)
        return rows, total

    async def get_forecast(self, user, org_context, forecast_id: str) -> ForecastResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        row = await self.forecast_repo.get_for_org(forecast_id, organization_id)
        if row is None:
            raise NexoraException("Forecast not found.", status_code=404)
        await self.audit_repo.log(
            action="forecast_viewed",
            resource_type="capacity_forecast",
            resource_id=forecast_id,
            user_id=user.id,
            details={"organization_id": organization_id},
        )
        await self.session.commit()
        return self._to_response(row)

    async def dashboard(self, user, org_context) -> CapacityDashboard:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        rows = await self.forecast_repo.list_recent(organization_id, limit=200)
        await self.audit_repo.log(
            action="dashboard_viewed",
            resource_type="capacity_forecast",
            resource_id=organization_id,
            user_id=user.id,
            details={"organization_id": organization_id, "forecasts": len(rows)},
        )
        await self.session.commit()

        # Latest forecast per resource_type for the resource summary.
        by_resource: dict[str, object] = {}
        for r in rows:  # rows are newest-first
            if r.resource_type not in by_resource:
                by_resource[r.resource_type] = r
        exhaustion_dates = [_aware(r.exhaustion_date) for r in rows if r.exhaustion_date]

        return CapacityDashboard(
            total_forecasts=len(rows),
            critical_count=sum(1 for r in rows if r.status == CapacityStatus.CRITICAL.value),
            warning_count=sum(1 for r in rows if r.status == CapacityStatus.WARNING.value),
            healthy_count=sum(1 for r in rows if r.status == CapacityStatus.HEALTHY.value),
            total_current_cost=round(sum(r.current_cost for r in rows), 2),
            total_projected_cost=round(sum(r.projected_cost for r in rows), 2),
            total_delta_cost=round(sum(r.delta_cost for r in rows), 2),
            soonest_exhaustion_date=min(exhaustion_dates) if exhaustion_dates else None,
            by_resource=[
                ResourceSummary(
                    resource_type=r.resource_type,
                    status=r.status,
                    current_utilization=r.current_utilization,
                    forecast_30d=r.forecast_30d,
                    exhaustion_date=r.exhaustion_date,
                    recommendation_action=r.recommendation_action,
                )
                for r in by_resource.values()
            ],
            recent_forecasts=[self._to_response(r) for r in rows[:25]],
        )

    @staticmethod
    def _to_response(row) -> ForecastResponse:
        tp = []
        if row.details and isinstance(row.details, dict):
            for p in row.details.get("trend_points", []):
                tp.append(TrendPoint(timestamp=p["timestamp"], utilization=p["utilization"]))
        resp = ForecastResponse.model_validate(row)
        resp.trend_points = tp
        return resp
