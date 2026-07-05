"""Sprint 41D — Deployment Risk Intelligence.

Predicts deployment risk BEFORE production impact, moving the platform from
"Investigate → Recommend → Remediate" to "Predict → Prevent → Investigate →
Remediate".

This is strictly **read-only**: it aggregates the organization's existing
history (deployment runs, incident investigations, remediation/rollback history)
and an optional *candidate* change-set, then produces a deterministic,
rules-based risk score (0–100) with full explanations. No model training, no
mutations, no deployment execution, no approvals.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError
from app.models.deployment import DeploymentStatus
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.deployment import DeploymentRunRepository
from app.repositories.incident import (
    IncidentInvestigationRepository,
    IncidentRemediationActionRepository,
)
from app.schemas.deployment_risk import (
    DeploymentRiskAnalyzeRequest,
    DeploymentRiskInsights,
    DeploymentRiskReason,
    DeploymentRiskReport,
    DeploymentRiskTrendPoint,
)
from app.tenancy.permissions import can_read_ai_teams

_FAILED_STATES = {DeploymentStatus.FAILED.value, DeploymentStatus.ROLLED_BACK.value}
_TERMINAL_STATES = {DeploymentStatus.DEPLOYED.value} | _FAILED_STATES


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _level(score: int) -> str:
    if score <= 30:
        return "LOW"
    if score <= 60:
        return "MEDIUM"
    if score <= 80:
        return "HIGH"
    return "CRITICAL"


class DeploymentRiskAnalyzer:
    """Pure, rules-based scorer. Given gathered history + a candidate change-set,
    it produces (score, reasons, likely_impact, recommended_actions)."""

    def score(
        self,
        *,
        insights: DeploymentRiskInsights,
        runs: list,
        incidents: list,
        provider: str | None,
        candidate: DeploymentRiskAnalyzeRequest | None,
    ) -> tuple[int, list[DeploymentRiskReason], list[str], list[str]]:
        reasons: list[DeploymentRiskReason] = []
        now = _now()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        # ---------------- historical factors ----------------
        recent_failures = [
            r for r in runs
            if r.status in _FAILED_STATES and (_aware(r.created_at) or now) >= week_ago
        ]
        if recent_failures:
            n = len(recent_failures)
            reasons.append(DeploymentRiskReason(
                factor="recent_deployment_failures",
                detail=f"{n} failed deployment{'s' if n != 1 else ''} in the last 7 days",
                weight=min(30, n * 12),
            ))

        recent_rollbacks = [
            r for r in runs
            if r.status == DeploymentStatus.ROLLED_BACK.value
            and (_aware(r.created_at) or now) >= week_ago
        ]
        if recent_rollbacks:
            n = len(recent_rollbacks)
            reasons.append(DeploymentRiskReason(
                factor="recent_rollbacks",
                detail=f"{n} rollback{'s' if n != 1 else ''} in the last 7 days",
                weight=min(25, n * 10),
            ))

        if insights.rollback_rate is not None and insights.rollback_rate > 20:
            reasons.append(DeploymentRiskReason(
                factor="high_rollback_rate",
                detail=f"Rollback rate is {insights.rollback_rate:.0f}%",
                weight=10,
            ))

        if insights.success_rate is not None and insights.success_rate < 80 and insights.total_deployments >= 3:
            reasons.append(DeploymentRiskReason(
                factor="low_success_rate",
                detail=f"Deployment success rate is {insights.success_rate:.0f}%",
                weight=10,
            ))

        # Incident correlation (optionally narrowed to the same provider).
        correlated = [
            i for i in incidents
            if (_aware(i.created_at) or now) >= month_ago
            and (provider is None or (i.suspected_provider or "").upper() == provider.upper())
        ]
        if correlated:
            n = len(correlated)
            reasons.append(DeploymentRiskReason(
                factor="incident_correlation",
                detail=f"{n} related incident{'s' if n != 1 else ''} in the last 30 days",
                weight=min(20, n * 8),
            ))
            latest = max(correlated, key=lambda i: _aware(i.created_at) or now)
            days = max(0, (now - (_aware(latest.created_at) or now)).days)
            reasons.append(DeploymentRiskReason(
                factor="prior_incident_pattern",
                detail=f"A similar deployment caused an incident {days} day{'s' if days != 1 else ''} ago",
                weight=10,
            ))

        # Repeated failure pattern for the same provider/app.
        groups: dict[tuple, int] = {}
        for r in runs:
            if r.status in _FAILED_STATES:
                key = (r.deployment_provider, r.project_id)
                groups[key] = groups.get(key, 0) + 1
        if any(c >= 2 for c in groups.values()):
            reasons.append(DeploymentRiskReason(
                factor="repeated_failure_pattern",
                detail="A repeated failure pattern was detected for this target",
                weight=12,
            ))

        # ---------------- candidate change-set factors ----------------
        cand = candidate or DeploymentRiskAnalyzeRequest()
        if cand.has_database_migration:
            reasons.append(DeploymentRiskReason(
                factor="database_migration", detail="Database migration detected", weight=18))
        if cand.has_infrastructure_changes:
            reasons.append(DeploymentRiskReason(
                factor="infrastructure_changes",
                detail="Infrastructure / Kubernetes manifest changes", weight=12))
        if cand.has_config_changes:
            reasons.append(DeploymentRiskReason(
                factor="configuration_changes", detail="Configuration changes detected", weight=8))
        if cand.production_only:
            reasons.append(DeploymentRiskReason(
                factor="production_only_change",
                detail="Production-only change with no staging validation", weight=10))
        if cand.changed_files > 30:
            reasons.append(DeploymentRiskReason(
                factor="large_change_set",
                detail=f"Large change set: {cand.changed_files} files changed", weight=12))
        elif cand.changed_files > 15:
            reasons.append(DeploymentRiskReason(
                factor="moderate_change_set",
                detail=f"Moderate change set: {cand.changed_files} files changed", weight=6))
        if cand.commit_count > 20:
            reasons.append(DeploymentRiskReason(
                factor="high_commit_volume",
                detail=f"High change volume: {cand.commit_count} commits", weight=8))

        score = min(100, sum(r.weight for r in reasons))
        if not reasons:
            reasons.append(DeploymentRiskReason(
                factor="no_signals",
                detail="No elevated risk signals detected from history or change-set",
                weight=0,
            ))

        impact = self._impact(reasons, provider, insights)
        actions = self._actions(score, reasons)
        return score, reasons, impact, actions

    def _impact(self, reasons, provider, insights: DeploymentRiskInsights) -> list[str]:
        factors = {r.factor for r in reasons}
        impact: list[str] = []
        if "database_migration" in factors:
            impact.append("Schema migration may lock tables or cause downtime")
        if "infrastructure_changes" in factors or (provider or "").upper() == "KUBERNETES":
            impact.append("Container restart risk during rollout")
        if {"incident_correlation", "prior_incident_pattern"} & factors:
            impact.append("API latency or error-rate increase based on past incidents")
        if {"recent_deployment_failures", "low_success_rate", "high_rollback_rate"} & factors:
            impact.append("Elevated chance of a failed rollout requiring rollback")
        if not impact:
            impact.append("Limited expected production impact")
        return impact

    def _actions(self, score: int, reasons) -> list[str]:
        factors = {r.factor for r in reasons}
        actions: list[str] = []
        if score > 60:
            actions.append("Deploy during a maintenance window")
            actions.append("Enable canary / progressive rollout")
            actions.append("Increase monitoring and alert coverage during rollout")
        if "database_migration" in factors:
            actions.append("Back up the database and rehearse the migration in staging")
        if "production_only_change" in factors:
            actions.append("Validate the change in staging before production")
        if {"recent_deployment_failures", "recent_rollbacks"} & factors:
            actions.append("Review the recent failed deployments before proceeding")
        actions.append("Have an approved rollback action ready before deploying")
        # De-duplicate while preserving order.
        seen = set()
        return [a for a in actions if not (a in seen or seen.add(a))]


class DeploymentRiskService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.run_repo = DeploymentRunRepository(session)
        self.investigation_repo = IncidentInvestigationRepository(session)
        self.action_repo = IncidentRemediationActionRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.analyzer = DeploymentRiskAnalyzer()

    def _ensure_read(self, user: User, org_context: OrgContext) -> None:
        if not user.is_superuser and (
            not org_context.role or not can_read_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    async def analyze(
        self,
        current_user: User,
        org_context: OrgContext,
        *,
        candidate: DeploymentRiskAnalyzeRequest | None = None,
        provider: str | None = None,
        environment: str | None = None,
        project_id: str | None = None,
        application: str | None = None,
    ) -> DeploymentRiskReport:
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)

        if candidate is not None:
            provider = candidate.provider or provider
            environment = candidate.environment or environment
            project_id = candidate.project_id or project_id
            application = candidate.application or application

        runs, _ = await self.run_repo.list_by_organization(
            organization_id, offset=0, limit=300
        )
        incidents, _ = await self.investigation_repo.list_for_org(
            organization_id, offset=0, limit=300
        )

        # Optional scope filters (non-secret target coordinates).
        if provider:
            runs = [r for r in runs if (r.deployment_provider or "").upper() == provider.upper()]
        if environment:
            runs = [r for r in runs if (r.environment or "") == environment]
        if project_id:
            runs = [r for r in runs if r.project_id == project_id]

        insights = self._build_insights(runs, incidents)
        score, reasons, impact, actions = self.analyzer.score(
            insights=insights,
            runs=runs,
            incidents=incidents,
            provider=provider,
            candidate=candidate,
        )
        trend = self._build_trend(runs, incidents)

        await self.audit_repo.log(
            action="deployment_risk_analyzed",
            resource_type="deployment_risk",
            resource_id=project_id or provider or "organization",
            user_id=current_user.id,
            details={
                "risk_score": score,
                "risk_level": _level(score),
                "provider": provider,
                "environment": environment,
                "candidate": candidate is not None,
            },
        )
        await self.session.commit()

        return DeploymentRiskReport(
            risk_score=score,
            risk_level=_level(score),
            provider=provider,
            environment=environment,
            application=application,
            reasons=reasons,
            insights=insights,
            likely_impact=impact,
            recommended_actions=actions,
            trend=trend,
        )

    # ----------------------------------------------------------- helpers
    def _build_insights(self, runs: list, incidents: list) -> DeploymentRiskInsights:
        terminal = [r for r in runs if r.status in _TERMINAL_STATES]
        success = [r for r in runs if r.status == DeploymentStatus.DEPLOYED.value]
        failed = [r for r in runs if r.status == DeploymentStatus.FAILED.value]
        rolled = [r for r in runs if r.status == DeploymentStatus.ROLLED_BACK.value]
        total = len(terminal)

        success_rate = round(len(success) / total * 100, 1) if total else None
        rollback_rate = round(len(rolled) / total * 100, 1) if total else None

        def _ts(r):
            return _aware(r.completed_at) or _aware(r.created_at)

        last_success = max((_ts(r) for r in success), default=None)
        last_failed = max((_ts(r) for r in (failed + rolled)), default=None)

        now = _now()
        month_ago = now - timedelta(days=30)
        recent_incidents = [i for i in incidents if (_aware(i.created_at) or now) >= month_ago]
        incident_freq = round(len(recent_incidents) / (30 / 7), 2) if incidents else None

        return DeploymentRiskInsights(
            total_deployments=total,
            successful_deployments=len(success),
            failed_deployments=len(failed),
            rolled_back_deployments=len(rolled),
            success_rate=success_rate,
            rollback_rate=rollback_rate,
            mttr_minutes=self._mttr(runs, incidents),
            incident_count=len(incidents),
            incident_frequency_per_week=incident_freq,
            last_successful_deployment=last_success,
            last_failed_deployment=last_failed,
        )

    def _mttr(self, runs: list, incidents: list) -> float | None:
        """Mean time to recovery: average minutes from a failed/rolled-back
        deployment to the next successful one. Falls back to completed incident
        investigation duration when deployment recovery pairs are unavailable."""
        ordered = sorted(
            [r for r in runs if r.status in _TERMINAL_STATES],
            key=lambda r: _aware(r.created_at) or _now(),
        )
        deltas: list[float] = []
        pending_fail: datetime | None = None
        for r in ordered:
            ts = _aware(r.created_at) or _now()
            if r.status in _FAILED_STATES and pending_fail is None:
                pending_fail = ts
            elif r.status == DeploymentStatus.DEPLOYED.value and pending_fail is not None:
                deltas.append((ts - pending_fail).total_seconds() / 60.0)
                pending_fail = None
        if deltas:
            return round(sum(deltas) / len(deltas), 1)

        durations: list[float] = []
        for i in incidents:
            if getattr(i, "status", None) == "COMPLETED":
                start = _aware(i.created_at)
                end = _aware(getattr(i, "updated_at", None))
                if start and end and end >= start:
                    durations.append((end - start).total_seconds() / 60.0)
        if durations:
            return round(sum(durations) / len(durations), 1)
        return None

    def _build_trend(self, runs: list, incidents: list) -> list[DeploymentRiskTrendPoint]:
        """Eight weekly buckets (oldest→newest) with a derived risk proxy."""
        now = _now()
        points: list[DeploymentRiskTrendPoint] = []
        for w in range(7, -1, -1):
            start = now - timedelta(days=7 * (w + 1))
            end = now - timedelta(days=7 * w)
            wk_runs = [r for r in runs if start <= (_aware(r.created_at) or now) < end]
            wk_fail = [r for r in wk_runs if r.status in _FAILED_STATES]
            wk_inc = [i for i in incidents if start <= (_aware(i.created_at) or now) < end]
            proxy = min(100, len(wk_fail) * 18 + len(wk_inc) * 8)
            label = end.strftime("%b %d")
            points.append(DeploymentRiskTrendPoint(
                period=label, score=proxy, deployments=len(wk_runs), failures=len(wk_fail)
            ))
        return points
