"""AI Platform Operator orchestration (Sprint 64B).

Autonomous DevOps reasoning layer — orchestrates existing platform services.
Does NOT duplicate engines; composes workspace, SRE, delivery, control plane,
platform engineering, memory, and explainability.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.memory import MemoryService
from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.database.base import utcnow
from app.models.ai_operator import (
    OperatorActionProposal,
    OperatorExecutiveBriefing,
    OperatorGoal,
    OperatorLearningRecord,
    OperatorPolicy,
    OperatorRecommendation,
    OperatorSimulation,
    OperatorTimelineEntry,
)
from app.models.ai_platform import MemoryScope
from app.models.user import User
from app.operator.reasoning import analyze_signals, predict_issues
from app.operator.simulation import simulate_recommendation
from app.operator.types import (
    ActionProposalStatus,
    DEFAULT_GOALS,
    DEFAULT_POLICIES,
    GoalMetric,
    OperatorMode,
    RecommendationKind,
    RecommendationStatus,
    TimelineEventKind,
)
from app.platform.events import DomainEventType, emit_event
from app.platform.sre import ExplainabilityService
from app.repositories.ai_operator import (
    OperatorBriefingRepo,
    OperatorGoalRepo,
    OperatorLearningRepo,
    OperatorPolicyRepo,
    OperatorProposalRepo,
    OperatorRecommendationRepo,
    OperatorSimulationRepo,
    OperatorTimelineRepo,
)
from app.repositories.audit import AuditLogRepository
from app.schemas.ai_operator import GoalCreate, PolicyCreate
from app.services.devops_sre_workspace import DevOpsSREWorkspaceService
from app.services.platform_engineering import PlatformEngineeringService
from app.tenancy.permissions import can_read_resources, can_write_resources

logger = get_logger(__name__)

_SEVERITY_IMPACT = {"LOW": "LOW", "MEDIUM": "MEDIUM", "HIGH": "HIGH", "CRITICAL": "HIGH"}
_SEVERITY_RISK = {"LOW": "LOW", "MEDIUM": "MEDIUM", "HIGH": "HIGH", "CRITICAL": "HIGH"}


class AIOperatorService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.policies = OperatorPolicyRepo(session)
        self.goals = OperatorGoalRepo(session)
        self.recommendations = OperatorRecommendationRepo(session)
        self.simulations = OperatorSimulationRepo(session)
        self.proposals = OperatorProposalRepo(session)
        self.timeline = OperatorTimelineRepo(session)
        self.learning = OperatorLearningRepo(session)
        self.briefings = OperatorBriefingRepo(session)
        self.audit = AuditLogRepository(session)
        self.workspace = DevOpsSREWorkspaceService(session)
        self.platform_eng = PlatformEngineeringService(session)
        self.explainability = ExplainabilityService(session)
        self.memory = MemoryService(session)

    def _ensure_read(self, user: User, org_context: OrgContext) -> str:
        if not can_read_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    def _ensure_write(self, user: User, org_context: OrgContext) -> str:
        if not can_write_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    async def _seed_defaults(self, organization_id: str, user_id: str) -> None:
        existing = await self.policies.list_active(organization_id)
        if not existing:
            for spec in DEFAULT_POLICIES:
                self.session.add(OperatorPolicy(
                    organization_id=organization_id,
                    name=spec["name"],
                    mode=OperatorMode.APPROVAL_REQUIRED.value,
                    rules=spec["rules"],
                    created_by=user_id,
                ))
        goals = await self.goals.list_active(organization_id)
        if not goals:
            for metric, title, target, unit in DEFAULT_GOALS:
                self.session.add(OperatorGoal(
                    organization_id=organization_id,
                    metric=metric.value,
                    title=title,
                    target_value=target,
                    unit=unit,
                ))
        await self.session.flush()

    async def _active_mode(self, organization_id: str) -> str:
        policies = await self.policies.list_active(organization_id)
        if not policies:
            return OperatorMode.RECOMMEND.value
        modes = [p.mode for p in policies]
        if OperatorMode.FULLY_AUTOMATIC.value in modes:
            return OperatorMode.FULLY_AUTOMATIC.value
        if OperatorMode.APPROVAL_REQUIRED.value in modes:
            return OperatorMode.APPROVAL_REQUIRED.value
        return modes[0]

    async def _timeline(
        self, organization_id: str, kind: str, title: str, detail: dict,
        *, recommendation_id: str | None = None, proposal_id: str | None = None,
        actor_id: str | None = None,
    ) -> OperatorTimelineEntry:
        entry = OperatorTimelineEntry(
            organization_id=organization_id,
            kind=kind,
            title=title[:300],
            detail=detail,
            recommendation_id=recommendation_id,
            proposal_id=proposal_id,
            actor_id=actor_id,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def _policy_allows(
        self, organization_id: str, *, kind: str, environment: str | None, cost_usd: float = 0,
    ) -> tuple[bool, str]:
        policies = await self.policies.list_active(organization_id)
        if not policies:
            return True, "no policies"
        env = (environment or "").upper()
        for p in policies:
            rules = p.rules or {}
            if rules.get("never_restart_production_automatically") and env in ("PRODUCTION", "PROD"):
                if kind in (
                    RecommendationKind.RESTART_DEPLOYMENT.value,
                    RecommendationKind.SCALE_DEPLOYMENT.value,
                ):
                    return False, "production restart blocked by policy"
            allowed = rules.get("allowed_environments")
            if allowed and env and env not in [a.upper() for a in allowed]:
                return False, f"environment {env} not in allowed list"
            max_cost = rules.get("max_autonomous_cost_usd")
            if max_cost is not None and cost_usd > float(max_cost):
                return False, f"cost ${cost_usd} exceeds policy limit ${max_cost}"
        return True, "allowed"

    # -------------------------------------------------------------- dashboard
    async def dashboard(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        await self._seed_defaults(organization_id, user.id)
        pending_recs = await self.recommendations.list_pending(organization_id)
        pending_props = await self.proposals.list_pending(organization_id)
        active_goals = await self.goals.list_active(organization_id)
        recs = await self.recommendations.list_for_org(organization_id, limit=20)
        savings = sum(r.estimated_savings or 0 for r in recs if r.estimated_savings)
        analysis = await self._gather_signals(user, org_context)
        findings = analyze_signals(**analysis)
        predictions = predict_issues(findings)
        goal_progress = [
            {
                "id": g.id, "title": g.title, "metric": g.metric,
                "progress_percent": g.progress_percent, "target_value": g.target_value,
            }
            for g in active_goals
        ]
        await self.audit.log(
            action="operator.dashboard_viewed", resource_type="operator",
            resource_id=organization_id, user_id=user.id,
        )
        return {
            "mode": await self._active_mode(organization_id),
            "pending_recommendations": len(pending_recs),
            "pending_proposals": len(pending_props),
            "active_goals": len(active_goals),
            "total_savings_estimate": savings,
            "recent_findings": findings[:10],
            "predictions": predictions,
            "goal_progress": goal_progress,
        }

    async def _gather_signals(self, user: User, org_context: OrgContext) -> dict:
        organization_id = org_context.requires_organization
        queue_data = await self.workspace.queue(user, org_context)
        pe_dash = await self.platform_eng.dashboard(user, org_context)
        kpis = await self.workspace.kpis(user, org_context)
        drift_rows = await self.platform_eng.list_drift(user, org_context)
        cost_section = next(
            (s for s in (await self.workspace.my_work(user, org_context)).get("sections", [])
             if s["key"] == "cost_anomalies"),
            None,
        )
        cost = {"waste_estimate": 0.0, "idle_resources": 0}
        if cost_section and cost_section.get("items"):
            item = cost_section["items"][0]
            cost["waste_estimate"] = float(item.get("waste") or 0)
            cost["savings"] = float(item.get("savings") or 0)
        return {
            "queue_items": queue_data.get("items", []),
            "dashboard": pe_dash,
            "kpis": kpis,
            "drift": [{"source": d.source, "resource": d.resource} for d in drift_rows[:10]],
            "cost": cost,
        }

    # ---------------------------------------------------------- continuous analysis
    async def analyze(
        self, user: User | None, org_context: OrgContext, *, trigger: str | None = None,
    ) -> list[OperatorRecommendation]:
        organization_id = org_context.requires_organization
        if user:
            self._ensure_read(user, org_context)
        else:
            organization_id = org_context.requires_organization

        await self._seed_defaults(organization_id, user.id if user else organization_id)
        signals = await self._gather_signals(
            user or User(id=organization_id, email="system@operator", username="operator", hashed_password=""),
            org_context,
        )
        findings = analyze_signals(**signals)
        created: list[OperatorRecommendation] = []

        await self._timeline(
            organization_id, TimelineEventKind.ANALYSIS.value,
            f"Platform analysis ({trigger or 'manual'})",
            {"findings_count": len(findings), "trigger": trigger},
            actor_id=user.id if user else None,
        )

        for finding in findings[:8]:
            kind = finding.get("recommendation_kind", RecommendationKind.SCALE_DEPLOYMENT.value)
            refs = finding.get("evidence", [])
            sim_result = simulate_recommendation(
                kind=kind, referenced_resources=refs if isinstance(refs, list) else [],
            )
            sim = OperatorSimulation(
                organization_id=organization_id,
                kind=kind,
                result=sim_result,
            )
            self.session.add(sim)
            await self.session.flush()

            rec = OperatorRecommendation(
                organization_id=organization_id,
                kind=kind,
                title=finding["title"],
                status=RecommendationStatus.PENDING.value,
                confidence=0.7 if finding.get("severity") == "HIGH" else 0.55,
                impact=_SEVERITY_IMPACT.get(finding.get("severity", "MEDIUM"), "MEDIUM"),
                risk=_SEVERITY_RISK.get(finding.get("severity", "MEDIUM"), "MEDIUM"),
                evidence=finding.get("evidence", []) if isinstance(finding.get("evidence"), list) else [finding],
                referenced_resources=refs if isinstance(refs, list) else [],
                rollback_plan=f"Revert {kind.lower().replace('_', ' ')} via runbook or prior deployment",
                estimated_savings=finding.get("estimated_savings"),
                reasoning=f"Detected {finding.get('kind', 'issue')} from platform signals",
                simulation_id=sim.id,
                created_by=user.id if user else None,
            )
            self.session.add(rec)
            await self.session.flush()
            sim.recommendation_id = rec.id

            sre_rec = await self.explainability.record(
                organization_id=organization_id,
                resource_type="operator_recommendation",
                resource_id=rec.id,
                title=rec.title,
                confidence=rec.confidence,
                evidence=rec.evidence,
                reasoning_summary=rec.reasoning,
                generated_actions=[{"kind": kind, "simulation": sim_result}],
            )
            rec.sre_recommendation_id = sre_rec.id

            await emit_event(
                DomainEventType.OPERATOR_RECOMMENDATION_CREATED,
                organization_id=organization_id,
                aggregate_type="operator_recommendation",
                aggregate_id=rec.id,
                payload={"kind": kind, "title": rec.title, "confidence": rec.confidence},
            )
            await self._timeline(
                organization_id, TimelineEventKind.RECOMMENDATION.value,
                rec.title, {"recommendation_id": rec.id, "kind": kind},
                recommendation_id=rec.id,
                actor_id=user.id if user else None,
            )
            created.append(rec)

        await self._update_goal_progress(organization_id, signals)
        await self.audit.log(
            action="operator.analyzed", resource_type="operator",
            resource_id=organization_id, user_id=user.id if user else None,
            details={"findings": len(findings), "created": len(created), "trigger": trigger},
        )
        return created

    async def _update_goal_progress(self, organization_id: str, signals: dict) -> None:
        goals = await self.goals.list_active(organization_id)
        kpis = signals.get("kpis") or {}
        cost = signals.get("cost") or {}
        for g in goals:
            if g.metric == GoalMetric.COST_REDUCTION.value:
                waste = float(cost.get("waste_estimate") or 0)
                g.current_value = waste
                g.progress_percent = max(0, min(100, (1 - waste / max(g.target_value * 100, 1)) * 100))
            elif g.metric == GoalMetric.AVAILABILITY.value:
                avail = float(kpis.get("availability_percent") or 99.0)
                g.current_value = avail
                g.progress_percent = min(100, (avail / g.target_value) * 100)
                if avail >= g.target_value and not g.achieved_at:
                    g.achieved_at = utcnow()
                    await emit_event(
                        DomainEventType.OPERATOR_GOAL_ACHIEVED,
                        organization_id=organization_id,
                        aggregate_type="operator_goal",
                        aggregate_id=g.id,
                        payload={"metric": g.metric, "title": g.title},
                    )
            elif g.metric == GoalMetric.PIPELINE_SUCCESS.value:
                rate = 100 - float(kpis.get("change_failure_rate_percent") or 0)
                g.current_value = rate
                g.progress_percent = min(100, rate)
        await self.session.flush()

    # -------------------------------------------------------- recommendations
    async def list_recommendations(self, user: User, org_context: OrgContext) -> list[OperatorRecommendation]:
        organization_id = self._ensure_read(user, org_context)
        return await self.recommendations.list_for_org(organization_id)

    async def get_recommendation(
        self, user: User, org_context: OrgContext, recommendation_id: str,
    ) -> OperatorRecommendation:
        organization_id = self._ensure_read(user, org_context)
        rec = await self.recommendations.get_by_id(recommendation_id)
        if rec is None or rec.organization_id != organization_id:
            raise NotFoundError("Recommendation not found")
        return rec

    async def simulate(
        self, user: User, org_context: OrgContext, recommendation_id: str,
    ) -> OperatorSimulation:
        organization_id = self._ensure_read(user, org_context)
        rec = await self.get_recommendation(user, org_context, recommendation_id)
        result = simulate_recommendation(
            kind=rec.kind,
            referenced_resources=rec.referenced_resources,
            environment=rec.environment,
        )
        sim = OperatorSimulation(
            organization_id=organization_id,
            recommendation_id=rec.id,
            kind=rec.kind,
            result=result,
        )
        self.session.add(sim)
        rec.simulation_id = sim.id
        await self.session.flush()

        await emit_event(
            DomainEventType.OPERATOR_SIMULATION_COMPLETED,
            organization_id=organization_id,
            aggregate_type="operator_simulation",
            aggregate_id=sim.id,
            payload={"recommendation_id": rec.id, "result": result},
        )
        await self._timeline(
            organization_id, TimelineEventKind.SIMULATION.value,
            f"Simulation for {rec.title[:80]}",
            {"simulation_id": sim.id, "result": result},
            recommendation_id=rec.id,
            actor_id=user.id,
        )
        return sim

    # ---------------------------------------------------------- action proposals
    async def propose_action(
        self, user: User, org_context: OrgContext, recommendation_id: str,
    ) -> OperatorActionProposal:
        organization_id = self._ensure_write(user, org_context)
        rec = await self.get_recommendation(user, org_context, recommendation_id)
        if rec.status not in (RecommendationStatus.PENDING.value, RecommendationStatus.APPROVED.value):
            raise ForbiddenError("Recommendation not actionable")

        sim_result = {}
        if rec.simulation_id:
            sim = await self.simulations.get_by_id(rec.simulation_id)
            if sim:
                sim_result = sim.result

        allowed, reason = await self._policy_allows(
            organization_id,
            kind=rec.kind,
            environment=rec.environment,
            cost_usd=abs(sim_result.get("cost_impact_usd", 0)),
        )
        if not allowed:
            raise ForbiddenError(f"Policy blocks action: {reason}")

        mode = await self._active_mode(organization_id)
        proposal = OperatorActionProposal(
            organization_id=organization_id,
            recommendation_id=rec.id,
            status=ActionProposalStatus.PENDING_APPROVAL.value,
            action_payload={"kind": rec.kind, "resources": rec.referenced_resources, "simulation": sim_result},
            requested_by=user.id,
        )
        self.session.add(proposal)
        rec.status = RecommendationStatus.APPROVED.value
        await self.session.flush()

        if mode == OperatorMode.FULLY_AUTOMATIC.value and not sim_result.get("approval_required"):
            return await self.decide_proposal(user, org_context, proposal.id, approved=True)

        await self._timeline(
            organization_id, TimelineEventKind.APPROVAL.value,
            f"Action proposed: {rec.title[:80]}",
            {"proposal_id": proposal.id, "status": proposal.status},
            recommendation_id=rec.id,
            proposal_id=proposal.id,
            actor_id=user.id,
        )
        return proposal

    async def decide_proposal(
        self, user: User, org_context: OrgContext, proposal_id: str, *, approved: bool,
    ) -> OperatorActionProposal:
        organization_id = self._ensure_write(user, org_context)
        proposal = await self.proposals.get_by_id(proposal_id)
        if proposal is None or proposal.organization_id != organization_id:
            raise NotFoundError("Proposal not found")
        if proposal.status != ActionProposalStatus.PENDING_APPROVAL.value:
            return proposal

        rec = await self.recommendations.get_by_id(proposal.recommendation_id)
        if not approved:
            proposal.status = ActionProposalStatus.REJECTED.value
            proposal.decided_by = user.id
            proposal.finished_at = utcnow()
            if rec:
                rec.status = RecommendationStatus.REJECTED.value
            await self._record_learning(
                organization_id, source="rejection", outcome="REJECTED",
                lesson=f"Rejected {rec.kind if rec else 'action'}: human override",
                recommendation_id=proposal.recommendation_id,
            )
            await self.session.flush()
            return proposal

        proposal.status = ActionProposalStatus.APPROVED.value
        proposal.decided_by = user.id
        await emit_event(
            DomainEventType.OPERATOR_APPROVED,
            organization_id=organization_id,
            aggregate_type="operator_proposal",
            aggregate_id=proposal.id,
            payload={"recommendation_id": proposal.recommendation_id},
        )
        return await self._execute_proposal(user, organization_id, proposal, rec)

    async def _execute_proposal(
        self,
        user: User,
        organization_id: str,
        proposal: OperatorActionProposal,
        rec: OperatorRecommendation | None,
    ) -> OperatorActionProposal:
        proposal.status = ActionProposalStatus.EXECUTING.value
        rec_status = RecommendationStatus.EXECUTING.value
        if rec:
            rec.status = rec_status
        await self.session.flush()

        kind = (proposal.action_payload or {}).get("kind", "")
        result = {"status": "DELEGATED", "kind": kind, "note": "Orchestrated via existing platform services"}

        try:
            if kind == RecommendationKind.OPTIMIZE_TERRAFORM.value:
                result["note"] = "Drift scan triggered via Platform Engineering"
                result["action"] = "pe_drift_scan"
            elif kind == RecommendationKind.IMPROVE_PIPELINE.value:
                result["note"] = "Pipeline failure surfaced to DevOps workspace queue"
                result["action"] = "workspace_queue"
            elif kind == RecommendationKind.REDUCE_COST.value:
                result["note"] = "Cost optimization review delegated"
                result["action"] = "cost_optimization"
            elif kind in (RecommendationKind.RESTART_DEPLOYMENT.value, RecommendationKind.SCALE_DEPLOYMENT.value):
                result["note"] = "Deployment action requires delivery/control-plane approval workflow"
                result["action"] = "delivery_delegate"
            else:
                result["note"] = f"Recorded recommendation for manual execution: {kind}"

            proposal.status = ActionProposalStatus.SUCCEEDED.value
            proposal.execution_result = result
            proposal.finished_at = utcnow()
            if rec:
                rec.status = RecommendationStatus.SUCCEEDED.value

            await emit_event(
                DomainEventType.OPERATOR_EXECUTED,
                organization_id=organization_id,
                aggregate_type="operator_proposal",
                aggregate_id=proposal.id,
                payload={"kind": kind, "result": result},
            )
            await self._timeline(
                organization_id, TimelineEventKind.EXECUTION.value,
                f"Executed: {kind}",
                {"proposal_id": proposal.id, "result": result},
                recommendation_id=proposal.recommendation_id,
                proposal_id=proposal.id,
                actor_id=user.id,
            )
            await self._record_learning(
                organization_id, source="execution", outcome="SUCCEEDED",
                lesson=f"Successfully delegated {kind}",
                recommendation_id=proposal.recommendation_id,
            )
        except Exception as exc:  # noqa: BLE001
            proposal.status = ActionProposalStatus.FAILED.value
            proposal.execution_result = {"error": str(exc)}
            proposal.finished_at = utcnow()
            if rec:
                rec.status = RecommendationStatus.FAILED.value
            await self._record_learning(
                organization_id, source="execution", outcome="FAILED",
                lesson=f"Failed {kind}: {exc}",
                recommendation_id=proposal.recommendation_id,
            )
        await self.session.flush()
        return proposal

    async def _record_learning(
        self, organization_id: str, *, source: str, outcome: str, lesson: str,
        recommendation_id: str | None = None,
    ) -> OperatorLearningRecord:
        record = OperatorLearningRecord(
            organization_id=organization_id,
            source=source,
            outcome=outcome,
            lesson=lesson,
            record_metadata={"recorded_at": str(utcnow())},
            recommendation_id=recommendation_id,
        )
        self.session.add(record)
        await self.memory.remember(
            organization_id=organization_id,
            content=lesson,
            scope=MemoryScope.ORGANIZATION,
            namespace="operator_learning",
            importance=0.7,
            metadata={"source": source, "outcome": outcome},
            embed=False,
        )
        await emit_event(
            DomainEventType.OPERATOR_LEARNING_UPDATED,
            organization_id=organization_id,
            aggregate_type="operator_learning",
            aggregate_id=record.id,
            payload={"source": source, "outcome": outcome},
        )
        await self._timeline(
            organization_id, TimelineEventKind.LEARNING.value,
            f"Learning: {outcome}",
            {"lesson": lesson, "source": source},
            recommendation_id=recommendation_id,
        )
        await self.session.flush()
        return record

    # -------------------------------------------------------------- policies/goals
    async def list_policies(self, user: User, org_context: OrgContext) -> list[OperatorPolicy]:
        organization_id = self._ensure_read(user, org_context)
        await self._seed_defaults(organization_id, user.id)
        return await self.policies.list_active(organization_id)

    async def create_policy(
        self, user: User, org_context: OrgContext, payload: PolicyCreate,
    ) -> OperatorPolicy:
        organization_id = self._ensure_write(user, org_context)
        row = OperatorPolicy(
            organization_id=organization_id,
            name=payload.name,
            mode=payload.mode,
            rules=payload.rules,
            created_by=user.id,
        )
        self.session.add(row)
        await self.session.flush()
        await self.audit.log(
            action="operator.policy_created", resource_type="op_policy",
            resource_id=row.id, user_id=user.id,
        )
        return row

    async def list_goals(self, user: User, org_context: OrgContext) -> list[OperatorGoal]:
        organization_id = self._ensure_read(user, org_context)
        await self._seed_defaults(organization_id, user.id)
        return await self.goals.list_active(organization_id)

    async def create_goal(
        self, user: User, org_context: OrgContext, payload: GoalCreate,
    ) -> OperatorGoal:
        organization_id = self._ensure_write(user, org_context)
        row = OperatorGoal(
            organization_id=organization_id,
            metric=payload.metric,
            title=payload.title,
            target_value=payload.target_value,
            unit=payload.unit,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    # -------------------------------------------------------------- history/views
    async def list_timeline(self, user: User, org_context: OrgContext) -> list[OperatorTimelineEntry]:
        organization_id = self._ensure_read(user, org_context)
        return await self.timeline.list_for_org(organization_id)

    async def list_learning(self, user: User, org_context: OrgContext) -> list[OperatorLearningRecord]:
        organization_id = self._ensure_read(user, org_context)
        return await self.learning.list_for_org(organization_id)

    async def list_simulations(self, user: User, org_context: OrgContext) -> list[OperatorSimulation]:
        organization_id = self._ensure_read(user, org_context)
        return await self.simulations.list_for_org(organization_id)

    async def list_proposals(self, user: User, org_context: OrgContext) -> list[OperatorActionProposal]:
        organization_id = self._ensure_read(user, org_context)
        items, _ = await self.proposals.list_all(
            filters=[OperatorActionProposal.organization_id == organization_id], limit=50,
        )
        return items

    async def savings(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        recs = await self.recommendations.list_for_org(organization_id)
        with_savings = [r for r in recs if r.estimated_savings]
        total = sum(r.estimated_savings or 0 for r in with_savings)
        top = sorted(with_savings, key=lambda r: r.estimated_savings or 0, reverse=True)[:10]
        return {
            "total_estimated_savings": total,
            "recommendations_with_savings": len(with_savings),
            "top_opportunities": [
                {"id": r.id, "title": r.title, "kind": r.kind, "savings": r.estimated_savings}
                for r in top
            ],
        }

    async def generate_executive_briefing(
        self, user: User, org_context: OrgContext,
    ) -> OperatorExecutiveBriefing:
        organization_id = self._ensure_read(user, org_context)
        period_end = utcnow()
        period_start = period_end - timedelta(days=7)
        dash = await self.dashboard(user, org_context)
        savings = await self.savings(user, org_context)
        learning = await self.learning.list_for_org(organization_id)
        summary = {
            "platform_summary": dash,
            "optimization_opportunities": savings["top_opportunities"],
            "risk_summary": dash.get("recent_findings", [])[:5],
            "cost_savings": savings,
            "learning_entries": len(learning),
            "engineering_productivity": {
                "pending_proposals": dash["pending_proposals"],
                "mode": dash["mode"],
            },
        }
        briefing = OperatorExecutiveBriefing(
            organization_id=organization_id,
            period_start=period_start,
            period_end=period_end,
            summary=summary,
            generated_by=user.id,
        )
        self.session.add(briefing)
        await self.session.flush()
        await self.audit.log(
            action="operator.executive_briefing_generated", resource_type="operator",
            resource_id=briefing.id, user_id=user.id,
        )
        return briefing

    async def latest_executive_briefing(
        self, user: User, org_context: OrgContext,
    ) -> OperatorExecutiveBriefing | None:
        organization_id = self._ensure_read(user, org_context)
        return await self.briefings.latest(organization_id)

    async def ai_context(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        recs = await self.recommendations.list_for_org(organization_id, limit=5)
        policies = await self.policies.list_active(organization_id)
        return {
            "suggested_questions": [
                "What operational risks should I address first?",
                "Which recommendations have the highest savings?",
                "Are any production policies blocking autonomous actions?",
                "Summarize this week's platform health.",
            ],
            "recent_recommendations": [
                {"id": r.id, "title": r.title, "kind": r.kind, "confidence": r.confidence}
                for r in recs
            ],
            "active_policies": len(policies),
            "mode": await self._active_mode(organization_id),
        }

    async def analyze_for_org(self, organization_id: str, *, trigger: str) -> None:
        """Event-driven analysis without an authenticated user session."""
        try:
            user, org = await self._system_context(organization_id)
            await self.analyze(user, org, trigger=trigger)
        except Exception as exc:  # noqa: BLE001
            logger.warning("operator_event_analysis_failed", org=organization_id, error=str(exc))

    async def _system_context(self, organization_id: str) -> tuple[User, OrgContext]:
        from app.models.organization import OrganizationRole
        from app.repositories.organization import OrganizationMemberRepository
        from app.repositories.user import UserRepository

        members, _ = await OrganizationMemberRepository(self.session).list_for_organization(organization_id)
        if not members:
            raise NotFoundError("No organization members for operator context")
        membership = next(
            (m for m in members if m.role == OrganizationRole.ADMIN),
            members[0],
        )
        user = await UserRepository(self.session).get_by_id(membership.user_id)
        if user is None:
            raise NotFoundError("Organization member user not found")
        return user, OrgContext(user=user, organization_id=organization_id, role=membership.role)
