"""Sprint 42D — Safe Deployment Intelligence (Canary & Pre-Deployment Risk Guard).

Advisory and approval-driven. Composes existing read-only signals into a single
pre-deployment safety verdict:

* 41D ``DeploymentRiskService`` → risk score (0–100) + historical insights
* 42C ``ServiceHealthService`` → availability, burn rate, error budget, open
  incidents for the target service
* open remediation actions (41B)

…and produces a safety score, readiness state (READY / AT_RISK / NOT_READY),
blast-radius estimate, canary/strategy recommendation, deployment-window
guidance, and guardrail warnings.

It NEVER executes, blocks, rolls back, or mutates a deployment. Every analysis is
org-scoped and audited.

Scoring
-------
safety_score = clamp(0..100) of:
    100
    − risk_score × 0.5
    − burn penalty (CRITICAL 25 / WARNING 12)
    − error-budget penalty (over budget 15 / <25% left 8)
    − open_incidents × 5 (cap 20)
    − 5 if open remediation actions
    − blast penalty (CRITICAL 10 / HIGH 5)
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NexoraException
from app.models.deployment_safety import (
    BlastRadiusLevel,
    CanaryStrategy,
    ReadinessState,
)
from app.models.incident import RemediationActionStatus
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.deployment_safety import DeploymentSafetyRepository
from app.repositories.incident import IncidentRemediationActionRepository
from app.schemas.deployment_risk import DeploymentRiskAnalyzeRequest
from app.schemas.deployment_safety import (
    BlastRadius,
    DeploymentSafetyAnalysisSummary,
    DeploymentSafetyDashboard,
    DeploymentSafetyReport,
    ReadinessCheck,
)
from app.services.deployment_risk import DeploymentRiskService
from app.services.service_health import ServiceHealthService
from app.tenancy.permissions import can_read_ai_teams

logger = structlog.get_logger(__name__)

_OPEN_ACTION_STATES = {
    RemediationActionStatus.PENDING_APPROVAL.value,
    RemediationActionStatus.APPROVED.value,
    RemediationActionStatus.EXECUTING.value,
}

# Canary ladder, safest last. The risk band selects an index; SLO pressure shifts
# the recommendation toward the safer (higher) end.
_CANARY_LADDER = [
    CanaryStrategy.FULL_ROLLOUT.value,
    CanaryStrategy.CANARY_25.value,
    CanaryStrategy.CANARY_10.value,
    CanaryStrategy.CANARY_5.value,
    CanaryStrategy.BLUE_GREEN.value,
]

_STRATEGY_LABEL = {
    "FULL_ROLLOUT": "Full rollout",
    "CANARY_25": "25% canary",
    "CANARY_10": "10% canary",
    "CANARY_5": "5% canary",
    "BLUE_GREEN": "Blue/Green deployment",
}


def _now() -> datetime:
    return datetime.now(UTC)


class DeploymentSafetyService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.risk_service = DeploymentRiskService(session)
        self.health_service = ServiceHealthService(session)
        self.action_repo = IncidentRemediationActionRepository(session)
        self.safety_repo = DeploymentSafetyRepository(session)
        self.audit_repo = AuditLogRepository(session)

    def _ensure_read(self, user: User, org_context: OrgContext) -> None:
        if not user.is_superuser and (
            not org_context.role or not can_read_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    # ------------------------------------------------------------------ analyze
    async def analyze(self, user: User, org_context: OrgContext, req) -> DeploymentSafetyReport:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)

        # 1) Risk (41D) — reuse the analyzer with the candidate change-set.
        candidate = DeploymentRiskAnalyzeRequest(
            provider=req.provider,
            environment=req.environment,
            project_id=req.project_id,
            application=req.service,
            commit_count=req.commit_count,
            changed_files=req.changed_files,
            has_database_migration=req.has_database_migration,
            has_infrastructure_changes=req.has_infrastructure_changes,
            has_config_changes=req.has_config_changes,
            production_only=req.production_only,
        )
        risk = await self.risk_service.analyze(user, org_context, candidate=candidate)

        # 2) SLO health (42C) — only if the service is catalogued.
        health = None
        dependents: list[str] = []
        service_tier = None
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
                all_services = await self.health_service.service_repo.list_for_org(organization_id)
                dependents = [
                    s.name
                    for s in all_services
                    if s.id != service_obj.id
                    and s.owner_team
                    and s.owner_team == service_obj.owner_team
                ]

        # 3) Open remediation actions.
        actions = await self.action_repo.list_for_org(organization_id, limit=500)
        open_actions = [a for a in actions if a.status in _OPEN_ACTION_STATES]

        # ---- derived health signals (degrade gracefully when uncatalogued) ----
        burn_status = health.burn_rate.status if (health and health.burn_rate) else "NORMAL"
        budget_pct = (
            health.error_budget.remaining_percentage
            if (health and health.error_budget)
            else None
        )
        open_incidents = health.open_incidents if health else 0
        availability_30d = (
            next((w.availability_percentage for w in health.availability if w.window == "30d"), 100.0)
            if health
            else None
        )
        health_score = health.health_score if health else None
        rollback_rate = risk.insights.rollback_rate
        success_rate = risk.insights.success_rate

        # ---- blast radius ----
        blast = self._blast_radius(
            req.service, service_tier, dependents, req.environment, risk.risk_score
        )

        # ---- safety score ----
        safety_score = self._safety_score(
            risk.risk_score, burn_status, budget_pct, open_incidents, bool(open_actions), blast.level
        )

        # ---- readiness checks ----
        checks = self._readiness_checks(
            open_incidents, burn_status, budget_pct, len(open_actions), health_score
        )
        readiness = self._readiness(checks, safety_score, risk.risk_level)

        # ---- canary strategy ----
        strategy, rationale = self._canary(
            risk.risk_score, burn_status, rollback_rate, open_incidents, readiness
        )

        # ---- deployment window ----
        window, avoid = self._deployment_window(open_incidents, burn_status)

        # ---- guardrail warnings ----
        warnings = self._guardrails(
            risk, budget_pct, rollback_rate, success_rate, availability_30d, health,
            len(open_actions), strategy, readiness,
        )

        recommendation = self._recommendation(readiness, strategy, blast.level)

        report = DeploymentSafetyReport(
            service=req.service,
            environment=req.environment,
            version=req.version,
            provider=req.provider,
            safety_score=safety_score,
            confidence=self._confidence(risk.insights.total_deployments, health is not None),
            readiness=readiness,
            recommendation=recommendation,
            risk_score=risk.risk_score,
            risk_level=risk.risk_level,
            blast_radius=blast,
            recommended_strategy=strategy,
            strategy_rationale=rationale,
            recommended_window=window,
            avoid_windows=avoid,
            readiness_checks=checks,
            warnings=warnings,
            history=risk.insights,
        )

        # Persist + audit.
        row = await self.safety_repo.create(
            organization_id=organization_id,
            service=req.service,
            environment=req.environment,
            version=req.version,
            provider=req.provider,
            safety_score=safety_score,
            confidence=report.confidence,
            readiness=readiness,
            blast_radius=blast.level,
            recommended_strategy=strategy,
            recommended_window=window,
            risk_score=risk.risk_score,
            risk_level=risk.risk_level,
            warnings=warnings,
            details=report.model_dump(mode="json"),
            created_by=user.id,
        )
        report.analysis_id = row.id
        report.created_at = row.created_at
        await self.audit_repo.log(
            action="deployment_safety_analyzed",
            resource_type="deployment_safety",
            resource_id=row.id,
            user_id=user.id,
            details={
                "organization_id": organization_id,
                "service": req.service,
                "environment": req.environment,
                "safety_score": safety_score,
                "readiness": readiness,
                "blast_radius": blast.level,
                "recommended_strategy": strategy,
                "risk_score": risk.risk_score,
            },
        )
        await self.session.commit()
        return report

    # ------------------------------------------------------------------ history
    async def list_analyses(self, user, org_context, *, limit: int = 100):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        return await self.safety_repo.list_for_org(organization_id, limit=limit)

    async def get_analysis(self, user, org_context, analysis_id: str):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        row = await self.safety_repo.get_for_org(analysis_id, organization_id)
        if row is None:
            raise NexoraException("Analysis not found.", status_code=404)
        return row

    async def dashboard(self, user, org_context) -> DeploymentSafetyDashboard:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        rows = await self.safety_repo.list_for_org(organization_id, limit=200)
        await self.audit_repo.log(
            action="deployment_safety_dashboard_viewed",
            resource_type="deployment_safety",
            resource_id=organization_id,
            user_id=user.id,
            details={"organization_id": organization_id, "analyses": len(rows)},
        )
        await self.session.commit()
        scores = [r.safety_score for r in rows]
        return DeploymentSafetyDashboard(
            total_analyses=len(rows),
            ready_count=sum(1 for r in rows if r.readiness == ReadinessState.READY.value),
            at_risk_count=sum(1 for r in rows if r.readiness == ReadinessState.AT_RISK.value),
            not_ready_count=sum(1 for r in rows if r.readiness == ReadinessState.NOT_READY.value),
            average_safety_score=round(sum(scores) / len(scores)) if scores else None,
            recent_analyses=[DeploymentSafetyAnalysisSummary.model_validate(r) for r in rows[:25]],
        )

    # ------------------------------------------------------------- calculations
    @staticmethod
    def _safety_score(risk_score, burn_status, budget_pct, open_incidents, has_open_actions, blast_level) -> int:
        score = 100.0
        score -= risk_score * 0.5
        score -= {"CRITICAL": 25, "WARNING": 12}.get(burn_status, 0)
        if budget_pct is not None:
            if budget_pct < 0:
                score -= 15
            elif budget_pct < 25:
                score -= 8
        score -= min(open_incidents * 5, 20)
        if has_open_actions:
            score -= 5
        score -= {"CRITICAL": 10, "HIGH": 5}.get(blast_level, 0)
        return int(max(0, min(100, round(score))))

    @staticmethod
    def _readiness_checks(open_incidents, burn_status, budget_pct, open_actions, health_score) -> list[ReadinessCheck]:
        checks: list[ReadinessCheck] = []

        if open_incidents == 0:
            checks.append(ReadinessCheck(name="Active incidents", status="PASS", detail="No active incidents on this service"))
        else:
            st = "FAIL" if burn_status == "CRITICAL" else "WARN"
            checks.append(ReadinessCheck(name="Active incidents", status=st, detail=f"{open_incidents} active incident(s) on this service"))

        checks.append(ReadinessCheck(
            name="Open remediation actions",
            status="PASS" if open_actions == 0 else "WARN",
            detail="None pending" if open_actions == 0 else f"{open_actions} remediation action(s) awaiting completion",
        ))

        if budget_pct is None:
            checks.append(ReadinessCheck(name="Error budget", status="PASS", detail="No SLO configured (not tracked)"))
        elif budget_pct < 0:
            checks.append(ReadinessCheck(name="Error budget", status="FAIL", detail="Error budget exhausted for the current window"))
        elif budget_pct < 25:
            checks.append(ReadinessCheck(name="Error budget", status="WARN", detail=f"Only {round(budget_pct)}% of error budget remaining"))
        else:
            checks.append(ReadinessCheck(name="Error budget", status="PASS", detail=f"{round(budget_pct)}% of error budget remaining"))

        burn_map = {"NORMAL": "PASS", "WARNING": "WARN", "CRITICAL": "FAIL"}
        checks.append(ReadinessCheck(
            name="Burn rate", status=burn_map.get(burn_status, "PASS"),
            detail=f"Error-budget burn rate is {burn_status.lower()}",
        ))

        if health_score is None:
            checks.append(ReadinessCheck(name="Service health", status="PASS", detail="Service not catalogued (not tracked)"))
        elif health_score >= 90:
            checks.append(ReadinessCheck(name="Service health", status="PASS", detail=f"Health score {health_score}/100"))
        elif health_score >= 70:
            checks.append(ReadinessCheck(name="Service health", status="WARN", detail=f"Health score {health_score}/100"))
        else:
            checks.append(ReadinessCheck(name="Service health", status="FAIL", detail=f"Health score {health_score}/100"))

        return checks

    @staticmethod
    def _readiness(checks, safety_score, risk_level) -> str:
        statuses = {c.status for c in checks}
        if "FAIL" in statuses or safety_score < 40:
            return ReadinessState.NOT_READY.value
        if "WARN" in statuses or safety_score < 70 or risk_level in ("HIGH", "CRITICAL"):
            return ReadinessState.AT_RISK.value
        return ReadinessState.READY.value

    def _canary(self, risk_score, burn_status, rollback_rate, open_incidents, readiness) -> tuple[str, str]:
        if risk_score <= 30:
            idx = 0
        elif risk_score <= 50:
            idx = 1
        elif risk_score <= 70:
            idx = 2
        elif risk_score <= 85:
            idx = 3
        else:
            idx = 4

        shift = 0
        bumps = []
        if burn_status == "WARNING":
            shift += 1
            bumps.append("elevated SLO burn")
        if burn_status == "CRITICAL":
            shift += 2
            bumps.append("critical SLO burn")
        if rollback_rate is not None and rollback_rate > 20:
            shift += 1
            bumps.append(f"rollback rate {rollback_rate:.0f}%")
        if open_incidents > 0:
            shift += 1
            bumps.append("active incidents")
        if readiness == ReadinessState.NOT_READY.value:
            shift += 2
            bumps.append("service not ready")

        idx = min(len(_CANARY_LADDER) - 1, idx + shift)
        strategy = _CANARY_LADDER[idx]
        label = _STRATEGY_LABEL[strategy]
        if strategy == CanaryStrategy.FULL_ROLLOUT.value:
            rationale = "Low risk and healthy SLOs — full rollout is acceptable."
        else:
            base = f"Risk score {risk_score} suggests a progressive rollout"
            if bumps:
                base += "; safer strategy due to " + ", ".join(bumps)
            rationale = f"{base}. Recommended: {label}."
        return strategy, rationale

    @staticmethod
    def _deployment_window(open_incidents, burn_status) -> tuple[str, list[str]]:
        avoid = ["Peak traffic hours (~12:00–20:00 local time)"]
        if open_incidents > 0:
            avoid.append("While incidents are active")
        if burn_status in ("WARNING", "CRITICAL"):
            avoid.append("During the current SLO burn period")
        if open_incidents > 0 or burn_status == "CRITICAL":
            window = "Defer deployment until active incidents resolve and SLO burn returns to normal."
        else:
            window = "Low-traffic maintenance window (~02:00–05:00 UTC), outside peak traffic."
        return window, avoid

    @staticmethod
    def _blast_radius(service, tier, dependents, environment, risk_score) -> BlastRadius:
        affected = [service] if service else []
        points = 0
        if tier == "TIER_1":
            points += 3
        elif tier == "TIER_2":
            points += 1
        if len(dependents) >= 5:
            points += 3
        elif len(dependents) >= 2:
            points += 2
        elif len(dependents) >= 1:
            points += 1
        if (environment or "").lower() == "production":
            points += 1
        if risk_score > 70:
            points += 2
        elif risk_score > 50:
            points += 1

        if points >= 6:
            level = BlastRadiusLevel.CRITICAL.value
        elif points >= 4:
            level = BlastRadiusLevel.HIGH.value
        elif points >= 2:
            level = BlastRadiusLevel.MEDIUM.value
        else:
            level = BlastRadiusLevel.LOW.value

        impact: list[str] = []
        if tier == "TIER_1":
            impact.append("Tier-1 service — customer-facing impact likely")
        if dependents:
            impact.append(f"{len(dependents)} dependent service(s) in the same team may be affected")
        if (environment or "").lower() == "production":
            impact.append("Production environment — changes reach live customers")
        if not impact:
            impact.append("Limited expected customer impact")

        return BlastRadius(
            level=level,
            affected_services=affected,
            dependent_services=dependents,
            customer_impact=impact,
        )

    @staticmethod
    def _guardrails(risk, budget_pct, rollback_rate, success_rate, availability_30d, health, open_actions, strategy, readiness) -> list[str]:
        w: list[str] = []
        if budget_pct is not None and budget_pct < 0:
            w.append("Service exceeded its error budget this period.")
        if rollback_rate is not None and rollback_rate > 20:
            w.append(f"Rollback rate exceeded 20% ({rollback_rate:.0f}%).")
        factors = {r.factor for r in risk.reasons}
        if {"incident_correlation", "prior_incident_pattern"} & factors:
            n = risk.insights.incident_count
            w.append(f"Recent deployments correlated with incidents ({n} in history).")
        if success_rate is not None and success_rate < 80:
            w.append(f"Deployment success rate is low ({success_rate:.0f}%).")
        if health is not None and availability_30d is not None:
            target = health.error_budget.target_percentage if health.error_budget else None
            if target is not None and availability_30d < target:
                w.append("Service availability is below its SLO target.")
        if open_actions:
            w.append(f"{open_actions} open remediation action(s) pending; resolve before deploying.")
        if strategy != CanaryStrategy.FULL_ROLLOUT.value:
            w.append("Canary / progressive rollout strongly recommended.")
        if readiness == ReadinessState.NOT_READY.value:
            w.append("Service is NOT READY for deployment — address failing readiness checks first.")
        return w

    @staticmethod
    def _recommendation(readiness, strategy, blast_level) -> str:
        label = _STRATEGY_LABEL.get(strategy, strategy)
        if readiness == ReadinessState.NOT_READY.value:
            return f"Hold deployment — service is NOT READY ({blast_level} blast radius). Resolve blocking checks, then deploy via {label}."
        if readiness == ReadinessState.AT_RISK.value:
            return f"Proceed with caution — deploy via {label} with heightened monitoring ({blast_level} blast radius)."
        return f"Safe to deploy — {label} ({blast_level} blast radius)."

    @staticmethod
    def _confidence(total_deployments, has_health) -> float:
        conf = 0.45
        if total_deployments >= 10:
            conf += 0.3
        elif total_deployments >= 3:
            conf += 0.2
        elif total_deployments >= 1:
            conf += 0.1
        if has_health:
            conf += 0.2
        return round(min(conf, 0.95), 2)
