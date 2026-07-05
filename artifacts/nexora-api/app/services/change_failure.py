"""Sprint 44C — Change Failure Prediction Engine.

Deterministic, rules-based prediction of how likely a candidate deployment/change
is to cause an incident — computed *before* deployment. No machine learning:
every point of the score is attributable to an inspectable, weighted factor.

Composition (all read-only)
---------------------------
* 41D ``DeploymentRiskService``  → risk score (embeds commit volume, file count,
  DB migrations, infra/config changes, prod flag, historical failure/incident
  correlation), plus insights: success rate, rollback rate, MTTR, incident count.
* 42C ``ServiceHealthService``   → SLO burn rate, error-budget remaining, open
  incidents, availability, health score, service tier.
* 44B dependency graph           → transitive dependents ⇒ expected blast radius.
* 40A/40C signals are surfaced through 41D's historical insights and reasons.

Scoring (failure_probability, 0–100)
------------------------------------
Starts at 0; each factor *adds* points (clamped to 0..100):

    deployment risk (41D)   round(risk_score × 0.40)        (0..40)
    rollback rate           >30:+12  >15:+7  >5:+3
    deploy success rate     <70:+12  <85:+6  <95:+2
    incident history        >=5:+10  >=2:+6  >=1:+3
    MTTR (recovery cost)    >240m:+5  >60m:+2
    SLO burn rate           CRITICAL:+12  WARNING:+6
    error budget remaining  <0:+10   <25%:+5
    open incidents          +4 each (cap 12)
    blast radius (44B)      CRITICAL:+8  HIGH:+5  MEDIUM:+2
    service tier            TIER_1:+5  TIER_2:+2

Change-set specifics (migrations / infra / config / large diff) are already
captured inside the 41D risk score, so they are *not* double-counted — they are
surfaced as ``likely_failure_modes`` and mitigation steps instead.

risk_level:  <20 LOW · <40 MEDIUM · <65 HIGH · else CRITICAL
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NexoraException
from app.models.change_failure import FailureRiskLevel
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.change_failure import ChangeFailurePredictionRepository
from app.schemas.change_failure import (
    ChangeFailureDashboard,
    ChangeFailurePredictionReport,
    ChangeFailurePredictionSummary,
    ContributingFactor,
)
from app.schemas.deployment_risk import DeploymentRiskAnalyzeRequest
from app.services.deployment_risk import DeploymentRiskService
from app.services.graph import GraphService
from app.services.service_health import ServiceHealthService
from app.tenancy.permissions import can_read_ai_teams

logger = structlog.get_logger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


class ChangeFailurePredictionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.risk_service = DeploymentRiskService(session)
        self.health_service = ServiceHealthService(session)
        self.graph = GraphService(session)
        self.pred_repo = ChangeFailurePredictionRepository(session)
        self.audit_repo = AuditLogRepository(session)

    def _ensure_read(self, user: User, org_context: OrgContext) -> None:
        if not user.is_superuser and (
            not org_context.role or not can_read_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    # ------------------------------------------------------------------ analyze
    async def analyze(self, user, org_context, req) -> ChangeFailurePredictionReport:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)

        # 1) Deployment risk (41D) — embeds the change-set + historical signals.
        candidate = DeploymentRiskAnalyzeRequest(
            provider=req.provider,
            environment=req.environment,
            project_id=req.project_id,
            application=req.service,
            commit_count=req.commit_count,
            changed_files=req.changed_files,
            pull_requests=req.pull_requests,
            has_database_migration=req.has_database_migration,
            has_infrastructure_changes=req.has_infrastructure_changes,
            has_config_changes=req.has_config_changes,
            production_only=req.production_only,
        )
        risk = await self.risk_service.analyze(user, org_context, candidate=candidate)
        ins = risk.insights

        # 2) Service health (42C) — only if the service is catalogued.
        health = None
        service_tier = None
        service_obj = None
        if req.service:
            service_obj = await self.health_service.service_repo.find_by_name(
                organization_id, req.service
            )
            if service_obj is not None:
                service_tier = service_obj.tier
                slos = await self.health_service.slo_repo.list_for_service(
                    service_obj.id, organization_id
                )
                health = await self.health_service._compute(
                    organization_id, service_obj, slos, full=False
                )

        burn_status = health.burn_rate.status if (health and health.burn_rate) else "NORMAL"
        budget_pct = (
            health.error_budget.remaining_percentage if (health and health.error_budget) else None
        )
        open_incidents = health.open_incidents if health else 0
        health_score = health.health_score if health else None
        availability_30d = (
            next((w.availability_percentage for w in health.availability if w.window == "30d"), None)
            if health
            else None
        )

        # 3) Blast radius (44B) — transitive dependents of the target service.
        dependents, blast_level = await self._blast_radius(
            organization_id, service_obj, service_tier, req.environment, risk.risk_score
        )

        # ---- assemble explainable factors ----
        factors = self._factors(
            risk_score=risk.risk_score,
            rollback_rate=ins.rollback_rate,
            success_rate=ins.success_rate,
            incident_count=ins.incident_count,
            mttr=ins.mttr_minutes,
            burn_status=burn_status,
            budget_pct=budget_pct,
            open_incidents=open_incidents,
            blast_level=blast_level,
            tier=service_tier,
        )
        probability = int(max(0, min(100, round(sum(f.points for f in factors)))))
        risk_level = self._risk_level(probability)
        confidence = self._confidence(ins.total_deployments, health is not None, len(dependents))

        top = sorted(factors, key=lambda f: f.points, reverse=True)
        top = [f for f in top if f.points > 0][:5]

        failure_modes = self._failure_modes(req, ins, burn_status, budget_pct, blast_level)
        impact_detail = self._customer_impact(
            req.service, service_tier, dependents, req.environment, blast_level
        )
        impact_summary = self._impact_summary(blast_level, len(dependents), service_tier)
        mitigations = self._mitigations(
            req, probability, burn_status, budget_pct, open_incidents, blast_level, ins, len(dependents)
        )

        signals = {
            "risk_score": risk.risk_score,
            "risk_level": risk.risk_level,
            "rollback_rate": ins.rollback_rate,
            "success_rate": ins.success_rate,
            "mttr_minutes": ins.mttr_minutes,
            "incident_count": ins.incident_count,
            "incident_frequency_per_week": ins.incident_frequency_per_week,
            "total_deployments": ins.total_deployments,
            "burn_status": burn_status,
            "error_budget_remaining_percentage": budget_pct,
            "open_incidents": open_incidents,
            "availability_30d": availability_30d,
            "health_score": health_score,
            "service_tier": service_tier,
            "dependent_services": dependents,
            "blast_radius": blast_level,
            "change_set": {
                "commit_count": req.commit_count,
                "changed_files": req.changed_files,
                "pull_requests": req.pull_requests,
                "has_database_migration": req.has_database_migration,
                "has_infrastructure_changes": req.has_infrastructure_changes,
                "has_config_changes": req.has_config_changes,
                "production_only": req.production_only,
            },
        }

        report = ChangeFailurePredictionReport(
            service=req.service,
            environment=req.environment,
            provider=req.provider,
            version=req.version,
            failure_probability=probability,
            confidence_score=confidence,
            risk_level=risk_level,
            top_contributing_factors=top,
            contributing_factors=factors,
            likely_failure_modes=failure_modes,
            expected_blast_radius=blast_level,
            expected_customer_impact=impact_summary,
            customer_impact_detail=impact_detail,
            recommended_mitigation_steps=mitigations,
            signals=signals,
        )

        row = await self.pred_repo.create(
            organization_id=organization_id,
            service=req.service,
            environment=req.environment,
            provider=req.provider,
            version=req.version,
            failure_probability=probability,
            confidence_score=confidence,
            risk_level=risk_level,
            expected_blast_radius=blast_level,
            expected_customer_impact=impact_summary,
            contributing_factors=[f.model_dump() for f in factors],
            mitigation_steps=mitigations,
            details=report.model_dump(mode="json"),
            created_by=user.id,
        )
        report.prediction_id = row.id
        report.created_at = row.created_at

        await self.audit_repo.log(
            action="change_failure_predicted",
            resource_type="change_failure_prediction",
            resource_id=row.id,
            user_id=user.id,
            details={
                "organization_id": organization_id,
                "service": req.service,
                "environment": req.environment,
                "failure_probability": probability,
                "risk_level": risk_level,
                "expected_blast_radius": blast_level,
            },
        )
        await self.session.commit()
        return report

    # ------------------------------------------------------------------ history
    async def list_predictions(self, user, org_context, *, limit: int = 100):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        rows = await self.pred_repo.list_for_org(organization_id, limit=limit)
        return [ChangeFailurePredictionSummary.model_validate(r) for r in rows]

    async def get_prediction(self, user, org_context, prediction_id: str) -> ChangeFailurePredictionReport:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        row = await self.pred_repo.get_for_org(prediction_id, organization_id)
        if row is None:
            raise NexoraException("Prediction not found.", status_code=404)
        report = ChangeFailurePredictionReport(**(row.details or {}))
        report.prediction_id = row.id
        report.created_at = row.created_at
        return report

    async def dashboard(self, user, org_context) -> ChangeFailureDashboard:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        rows = await self.pred_repo.list_for_org(organization_id, limit=200)
        await self.audit_repo.log(
            action="change_failure_dashboard_viewed",
            resource_type="change_failure_prediction",
            resource_id=organization_id,
            user_id=user.id,
            details={"organization_id": organization_id, "predictions": len(rows)},
        )
        await self.session.commit()
        probs = [r.failure_probability for r in rows]
        summaries = [ChangeFailurePredictionSummary.model_validate(r) for r in rows]
        highest = sorted(summaries, key=lambda s: s.failure_probability, reverse=True)[:10]
        return ChangeFailureDashboard(
            total_predictions=len(rows),
            low_count=sum(1 for r in rows if r.risk_level == FailureRiskLevel.LOW.value),
            medium_count=sum(1 for r in rows if r.risk_level == FailureRiskLevel.MEDIUM.value),
            high_count=sum(1 for r in rows if r.risk_level == FailureRiskLevel.HIGH.value),
            critical_count=sum(1 for r in rows if r.risk_level == FailureRiskLevel.CRITICAL.value),
            average_failure_probability=round(sum(probs) / len(probs)) if probs else None,
            highest_risk=highest,
            recent_predictions=summaries[:25],
        )

    # ------------------------------------------------------------- calculations
    async def _blast_radius(self, organization_id, service_obj, tier, environment, risk_score):
        """Return (dependent_service_names, blast_level) using the 44B graph."""
        dependents: list[str] = []
        if service_obj is not None:
            services = await self.health_service.service_repo.list_for_org(organization_id)
            by_id = {s.id: s for s in services}
            g = await self.graph.service_adjacency(organization_id)
            _, transitive = g.dependents(service_obj.id)
            dependents = [by_id[i].name for i in transitive if i in by_id]

        points = 0
        if tier == "TIER_1":
            points += 3
        elif tier == "TIER_2":
            points += 1
        n = len(dependents)
        if n >= 5:
            points += 3
        elif n >= 2:
            points += 2
        elif n >= 1:
            points += 1
        if (environment or "").lower() == "production":
            points += 1
        if risk_score > 70:
            points += 2
        elif risk_score > 50:
            points += 1

        if points >= 6:
            level = "CRITICAL"
        elif points >= 4:
            level = "HIGH"
        elif points >= 2:
            level = "MEDIUM"
        else:
            level = "LOW"
        return dependents, level

    @staticmethod
    def _factors(*, risk_score, rollback_rate, success_rate, incident_count, mttr,
                 burn_status, budget_pct, open_incidents, blast_level, tier) -> list[ContributingFactor]:
        f: list[ContributingFactor] = []

        risk_pts = round(risk_score * 0.40)
        f.append(ContributingFactor(
            factor="Deployment risk score (41D)",
            detail=f"Risk score {risk_score}/100 (embeds change-set size, migrations, infra/config "
                   f"changes, and historical failure correlation) → +{risk_pts}",
            points=risk_pts, category="deployment_risk",
        ))

        if rollback_rate is not None:
            pts = 12 if rollback_rate > 30 else 7 if rollback_rate > 15 else 3 if rollback_rate > 5 else 0
            if pts:
                f.append(ContributingFactor(
                    factor="Rollback frequency",
                    detail=f"Historical rollback rate {rollback_rate:.0f}% → +{pts}",
                    points=pts, category="history",
                ))

        if success_rate is not None:
            pts = 12 if success_rate < 70 else 6 if success_rate < 85 else 2 if success_rate < 95 else 0
            if pts:
                f.append(ContributingFactor(
                    factor="Deployment success rate",
                    detail=f"Historical success rate {success_rate:.0f}% → +{pts}",
                    points=pts, category="history",
                ))

        pts = 10 if incident_count >= 5 else 6 if incident_count >= 2 else 3 if incident_count >= 1 else 0
        if pts:
            f.append(ContributingFactor(
                factor="Incident history",
                detail=f"{incident_count} incident(s) correlated with this scope → +{pts}",
                points=pts, category="incident",
            ))

        if mttr is not None:
            pts = 5 if mttr > 240 else 2 if mttr > 60 else 0
            if pts:
                f.append(ContributingFactor(
                    factor="Mean time to recovery (MTTR)",
                    detail=f"MTTR {mttr:.0f}m — slow recovery raises effective risk → +{pts}",
                    points=pts, category="incident",
                ))

        pts = {"CRITICAL": 12, "WARNING": 6}.get(burn_status, 0)
        if pts:
            f.append(ContributingFactor(
                factor="SLO burn rate",
                detail=f"Error-budget burn is {burn_status} → +{pts}",
                points=pts, category="slo",
            ))

        if budget_pct is not None:
            pts = 10 if budget_pct < 0 else 5 if budget_pct < 25 else 0
            if pts:
                detail = ("Error budget already exhausted" if budget_pct < 0
                          else f"Only {round(budget_pct)}% of error budget remaining")
                f.append(ContributingFactor(
                    factor="Error budget remaining",
                    detail=f"{detail} → +{pts}", points=pts, category="slo",
                ))

        if open_incidents > 0:
            pts = min(open_incidents * 4, 12)
            f.append(ContributingFactor(
                factor="Active incidents",
                detail=f"{open_incidents} active incident(s) on this service → +{pts}",
                points=pts, category="incident",
            ))

        pts = {"CRITICAL": 8, "HIGH": 5, "MEDIUM": 2}.get(blast_level, 0)
        if pts:
            f.append(ContributingFactor(
                factor="Blast radius (44B)",
                detail=f"{blast_level} blast radius across dependent services → +{pts}",
                points=pts, category="blast_radius",
            ))

        pts = 5 if tier == "TIER_1" else 2 if tier == "TIER_2" else 0
        if pts:
            f.append(ContributingFactor(
                factor="Service tier",
                detail=f"{tier} service → +{pts}", points=pts, category="service",
            ))

        return f

    @staticmethod
    def _risk_level(probability: int) -> str:
        if probability < 20:
            return FailureRiskLevel.LOW.value
        if probability < 40:
            return FailureRiskLevel.MEDIUM.value
        if probability < 65:
            return FailureRiskLevel.HIGH.value
        return FailureRiskLevel.CRITICAL.value

    @staticmethod
    def _confidence(total_deployments, has_health, dependents) -> float:
        conf = 0.40
        if total_deployments >= 10:
            conf += 0.30
        elif total_deployments >= 3:
            conf += 0.20
        elif total_deployments >= 1:
            conf += 0.10
        if has_health:
            conf += 0.20
        if dependents > 0:
            conf += 0.05
        return round(min(conf, 0.95), 2)

    @staticmethod
    def _failure_modes(req, ins, burn_status, budget_pct, blast_level) -> list[str]:
        modes: list[str] = []
        if req.has_database_migration:
            modes.append("Schema migration failure — lock contention, long-running or irreversible migration")
        if req.has_infrastructure_changes:
            modes.append("Infrastructure change failure — provisioning error, drift, or capacity shortfall")
        if req.has_config_changes:
            modes.append("Misconfiguration — bad env var / feature flag / secret reference")
        if (req.commit_count or 0) >= 20 or (req.changed_files or 0) >= 50:
            modes.append("Large change-set — wide regression surface and harder rollback")
        if ins.rollback_rate is not None and ins.rollback_rate > 15:
            modes.append("Repeat rollback — this scope has a history of being reverted")
        if ins.success_rate is not None and ins.success_rate < 85:
            modes.append("Pipeline instability — elevated historical deploy failure rate")
        if burn_status in ("WARNING", "CRITICAL") or (budget_pct is not None and budget_pct < 25):
            modes.append("Deploying into a degraded SLO window — limited error budget to absorb a regression")
        if blast_level in ("HIGH", "CRITICAL"):
            modes.append("Cascading failure — dependent services impacted if this change regresses")
        if not modes:
            modes.append("Standard regression risk — no elevated structural failure modes detected")
        return modes

    @staticmethod
    def _customer_impact(service, tier, dependents, environment, blast_level) -> list[str]:
        impact: list[str] = []
        if tier == "TIER_1":
            impact.append("Tier-1 service — direct customer-facing impact likely")
        if dependents:
            preview = ", ".join(dependents[:5]) + ("…" if len(dependents) > 5 else "")
            impact.append(f"{len(dependents)} dependent service(s) may be impacted: {preview}")
        if (environment or "").lower() == "production":
            impact.append("Production environment — changes reach live customers")
        if blast_level in ("HIGH", "CRITICAL"):
            impact.append(f"{blast_level} blast radius — prepare a rollback runbook and notify owners")
        if not impact:
            impact.append("Limited expected customer impact")
        return impact

    @staticmethod
    def _impact_summary(blast_level, dependents, tier) -> str:
        tier_txt = f" on a {tier} service" if tier else ""
        return (
            f"{blast_level} expected customer impact{tier_txt}; "
            f"{dependents} dependent service(s) in the blast radius."
        )

    @staticmethod
    def _mitigations(req, probability, burn_status, budget_pct, open_incidents,
                     blast_level, ins, dependents) -> list[str]:
        m: list[str] = []
        if probability >= 65:
            m.append("Hold or stage this change — failure probability is high; require a second reviewer.")
        wants_canary = (
            probability >= 30
            or req.has_database_migration
            or req.has_infrastructure_changes
            or (req.commit_count or 0) >= 20
            or (req.changed_files or 0) >= 50
            or blast_level in ("HIGH", "CRITICAL")
        )
        if wants_canary:
            m.append("Use a progressive canary rollout (5–10%) with automated rollback on error-rate spike.")
        if req.has_database_migration:
            m.append("Run the migration as a separate, reversible step; verify on a replica/staging first.")
        if req.has_infrastructure_changes:
            m.append("Apply infra changes via reviewed plan/apply; stage in non-production before prod.")
        if req.has_config_changes:
            m.append("Validate configuration in staging and gate the change behind a feature flag.")
        if (req.commit_count or 0) >= 20 or (req.changed_files or 0) >= 50:
            m.append("Split the change-set into smaller, independently deployable increments.")
        if burn_status in ("WARNING", "CRITICAL") or (budget_pct is not None and budget_pct < 25):
            m.append("Defer until SLO burn returns to normal and error budget recovers.")
        if open_incidents > 0:
            m.append("Resolve active incidents on this service before deploying.")
        if blast_level in ("HIGH", "CRITICAL") and dependents:
            m.append(f"Notify owners of {dependents} dependent service(s) and prepare a rollback runbook.")
        if ins.success_rate is not None and ins.success_rate < 85:
            m.append("Stabilize the pipeline — add pre-deploy smoke tests and health checks.")
        m.append("Enable heightened monitoring (error rate, latency, saturation) during and after rollout.")
        return m
