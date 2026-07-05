"""Sprint 52C.1 — Demo Scenario Engine.

Manages the lifecycle of demo scenarios: catalogue seeding, scenario execution,
replay, and reset.  All data produced is purely synthetic — no real credentials,
no cloud access, no production integrations.

Scenario catalogue (5 built-in types):

  CHECKOUT_OUTAGE   GitHub deploy → K8s rollout → CrashLoopBackOff → Alert
                    → Incident → Timeline → RCA → Recommendations → Remediation
                    → Postmortem
  DATABASE_LATENCY  Slow queries → Latency alert → SLO burn → Capacity warning
                    → Investigation → Recommendations
  MEMORY_LEAK       Memory growth → OOM events → Restarts → Customer impact
                    → Investigation
  BAD_DEPLOYMENT    Large change set → Risk analysis → Failure prediction
                    → Deployment safety
  COST_EXPLOSION    Idle resources → Capacity forecast → Cost optimisation

Strictly additive.  Reuses existing incident/alert/SLO/deployment models.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.capacity import CapacityForecast
from app.models.cost_optimization import CostOptimizationAnalysis
from app.models.demo_scenario import (
    DemoScenario,
    DemoScenarioRun,
    ScenarioRunStatus,
    ScenarioStatus,
    ScenarioType,
)
from app.models.deployment_safety import DeploymentSafetyAnalysis
from app.models.incident import (
    DeploymentChangeEvent,
    IncidentInvestigation,
    IncidentInvestigationStep,
    IncidentRecommendation,
    IncidentRemediationAction,
    IncidentRemediationApproval,
    IncidentTimelineEvent,
    MonitoringAlert,
)
from app.models.postmortem import IncidentPostmortem
from app.models.user import User
from app.models.war_room import WarRoom, WarRoomMessage
from app.repositories.audit import AuditLogRepository
from app.repositories.organization import (
    OrganizationMemberRepository,
    OrganizationRepository,
)

logger = get_logger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Built-in scenario definitions
# ---------------------------------------------------------------------------

_BUILTIN_SCENARIOS: dict[str, dict[str, Any]] = {
    ScenarioType.CHECKOUT_OUTAGE: {
        "name": "Checkout Outage",
        "description": (
            "A bad GitHub deployment introduces a null-pointer path in the checkout "
            "service that causes CrashLoopBackOff, triggers a CRITICAL alert, spawns "
            "an incident investigation, builds a timeline with change-event correlation, "
            "produces root-cause analysis, generates remediation recommendations, "
            "executes a rollback, and closes with a postmortem."
        ),
        "template_key": "ecommerce",
        "flow_steps": [
            {"step": 1, "name": "GitHub Deployment", "system": "GITHUB",
             "description": "Deployment of checkout-service v2.3.1 triggered via PR merge."},
            {"step": 2, "name": "Kubernetes Rollout", "system": "KUBERNETES",
             "description": "New pods roll out; liveness probe failures detected within 60 s."},
            {"step": 3, "name": "CrashLoopBackOff", "system": "KUBERNETES",
             "description": "Pod enters CrashLoopBackOff; error rate crosses 5% threshold."},
            {"step": 4, "name": "Alert Fired", "system": "PROMETHEUS",
             "description": "CRITICAL alert: checkout-service HTTP 5xx > 5% for 2 min."},
            {"step": 5, "name": "Incident Opened", "system": "NEXORA",
             "description": "AI SRE Lead opens incident investigation automatically."},
            {"step": 6, "name": "Timeline Built", "system": "NEXORA",
             "description": "Change events correlated; deployment identified as trigger."},
            {"step": 7, "name": "Root Cause Identified", "system": "NEXORA",
             "description": "Null payment-token path introduced in v2.3.1 confirmed."},
            {"step": 8, "name": "Recommendations Generated", "system": "NEXORA",
             "description": "Roll back to v2.2.9 recommended with confidence 94%."},
            {"step": 9, "name": "Remediation Executed", "system": "KUBERNETES",
             "description": "Rollback approved and applied; error rate returns to baseline."},
            {"step": 10, "name": "Postmortem Generated", "system": "NEXORA",
             "description": "Auto-generated postmortem with action items and lessons learned."},
        ],
    },
    ScenarioType.DATABASE_LATENCY: {
        "name": "Database Latency Surge",
        "description": (
            "Slow queries on the orders-db cause p95 latency to triple, "
            "triggering SLO burn-rate alerts and a capacity warning before the "
            "AI team correlates root cause to a missing index."
        ),
        "template_key": "ecommerce",
        "flow_steps": [
            {"step": 1, "name": "Slow Queries Detected", "system": "DATADOG",
             "description": "p95 query latency on orders-db exceeds 500 ms."},
            {"step": 2, "name": "Latency Alert", "system": "PROMETHEUS",
             "description": "HIGH alert: orders-db p95 latency > 500 ms for 5 min."},
            {"step": 3, "name": "SLO Burn-Rate Spike", "system": "NEXORA",
             "description": "Checkout SLO error-budget burn rate hits 4× in 1 h window."},
            {"step": 4, "name": "Capacity Warning", "system": "NEXORA",
             "description": "CPU saturation forecast reaches critical threshold in 48 h."},
            {"step": 5, "name": "Investigation Opened", "system": "NEXORA",
             "description": "Database Reliability AI agent analyses query plans."},
            {"step": 6, "name": "Root Cause Identified", "system": "NEXORA",
             "description": "Missing composite index on (order_id, status) confirmed."},
            {"step": 7, "name": "Recommendations Generated", "system": "NEXORA",
             "description": "Add index; scale read replica; enable query cache."},
        ],
    },
    ScenarioType.MEMORY_LEAK: {
        "name": "Memory Leak — Payment Gateway",
        "description": (
            "Memory usage on the payment-gateway service grows 3 % per hour, "
            "eventually triggering OOM kills, pod restarts and measurable customer "
            "impact before the AI team isolates the leak to a connection pool."
        ),
        "template_key": "ecommerce",
        "flow_steps": [
            {"step": 1, "name": "Memory Growth Detected", "system": "PROMETHEUS",
             "description": "payment-gateway RSS memory up 3 % / h over 6 h."},
            {"step": 2, "name": "OOM Events", "system": "KUBERNETES",
             "description": "OOMKilled events appear in pod events every ~2 h."},
            {"step": 3, "name": "Pod Restarts", "system": "KUBERNETES",
             "description": "Restart count reaches 5; availability SLO at risk."},
            {"step": 4, "name": "Customer Impact Alert", "system": "DATADOG",
             "description": "Payment success rate drops 1.2% — user-visible degradation."},
            {"step": 5, "name": "Investigation Opened", "system": "NEXORA",
             "description": "SRE Lead & Kubernetes Specialist investigate."},
            {"step": 6, "name": "Root Cause Identified", "system": "NEXORA",
             "description": "HTTP client connection pool not closing idle connections."},
            {"step": 7, "name": "Remediation Recommended", "system": "NEXORA",
             "description": "Patch connection pool + rolling restart recommended."},
        ],
    },
    ScenarioType.BAD_DEPLOYMENT: {
        "name": "High-Risk Deployment Blocked",
        "description": (
            "A large change set targeting a Tier-1 service triggers the deployment "
            "safety analyser, which predicts high failure probability and recommends "
            "a canary rollout strategy with an explicit approval gate."
        ),
        "template_key": "ecommerce",
        "flow_steps": [
            {"step": 1, "name": "Large Change Set", "system": "GITHUB",
             "description": "PR #2041 touches 14 files across checkout-service core paths."},
            {"step": 2, "name": "Risk Analysis", "system": "NEXORA",
             "description": "Deployment Safety Analyser scores risk 78/100 (HIGH)."},
            {"step": 3, "name": "Failure Prediction", "system": "NEXORA",
             "description": "Model predicts 34% probability of availability regression."},
            {"step": 4, "name": "Strategy Recommended", "system": "NEXORA",
             "description": "CANARY_10 strategy recommended; deployment window Tue–Thu 10–15 h."},
            {"step": 5, "name": "Approval Gate Raised", "system": "NEXORA",
             "description": "OWNER approval required before promotion past 10% canary."},
        ],
    },
    ScenarioType.COST_EXPLOSION: {
        "name": "Cost Explosion — Idle Resources",
        "description": (
            "Over-provisioned nodes and idle dev/staging workloads drive monthly "
            "cloud spend 28 % above budget.  The cost optimisation engine identifies "
            "$14 k/month of recoverable waste."
        ),
        "template_key": "ecommerce",
        "flow_steps": [
            {"step": 1, "name": "Idle Resources Detected", "system": "NEXORA",
             "description": "3 nodes at < 10 % CPU for 72 h; 4 over-provisioned deployments."},
            {"step": 2, "name": "Capacity Forecast", "system": "NEXORA",
             "description": "30-day forecast shows spend reaching $67 k without action."},
            {"step": 3, "name": "Waste Analysis", "system": "NEXORA",
             "description": "Estimated waste: $14 820/month (28 % of total spend)."},
            {"step": 4, "name": "Cost Optimisation Plan", "system": "NEXORA",
             "description": "Right-size 4 deployments; schedule 3 idle nodes for decommission."},
            {"step": 5, "name": "Annual Savings Projection", "system": "NEXORA",
             "description": "Implementing plan saves $177 840/year (optimisation score 82)."},
        ],
    },
}


class DemoScenarioService:
    """Create, list, run, replay, reset demo scenarios for an organisation."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.org_repo = OrganizationRepository(session)
        self.member_repo = OrganizationMemberRepository(session)
        self.audit_repo = AuditLogRepository(session)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    async def _add(self, model, **kwargs):
        obj = model(**kwargs)
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def _get_scenario(self, scenario_id: str, org_id: str) -> DemoScenario:
        result = await self.session.execute(
            select(DemoScenario).where(
                DemoScenario.id == scenario_id,
                DemoScenario.organization_id == org_id,
            )
        )
        s = result.scalar_one_or_none()
        if not s:
            raise NotFoundError("DemoScenario", scenario_id)
        return s

    async def _get_run(self, run_id: str, org_id: str) -> DemoScenarioRun:
        result = await self.session.execute(
            select(DemoScenarioRun).where(
                DemoScenarioRun.id == run_id,
                DemoScenarioRun.organization_id == org_id,
            )
        )
        r = result.scalar_one_or_none()
        if not r:
            raise NotFoundError("DemoScenarioRun", run_id)
        return r

    def _check_org_access(self, membership) -> None:
        if not membership:
            raise ForbiddenError("Not a member of this organisation")

    # ------------------------------------------------------------------ #
    # Catalogue helpers
    # ------------------------------------------------------------------ #
    async def _scenario_count(self, org_id: str) -> int:
        r = await self.session.execute(
            select(func.count()).select_from(DemoScenario)
            .where(DemoScenario.organization_id == org_id)
        )
        return int(r.scalar() or 0)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def seed_for_org(self, org_id: str, user: User) -> list[dict]:
        """Idempotently seed all 5 built-in scenarios for *org_id*."""
        existing_result = await self.session.execute(
            select(DemoScenario.scenario_type)
            .where(DemoScenario.organization_id == org_id, DemoScenario.is_builtin == True)  # noqa: E712
        )
        existing_types = {r for (r,) in existing_result.all()}
        created = []
        for stype, spec in _BUILTIN_SCENARIOS.items():
            if stype in existing_types:
                continue
            s = await self._add(
                DemoScenario,
                organization_id=org_id,
                scenario_type=stype,
                name=spec["name"],
                description=spec["description"],
                flow_steps=spec["flow_steps"],
                template_key=spec.get("template_key"),
                status=ScenarioStatus.AVAILABLE.value,
                run_count=0,
                is_builtin=True,
                created_by=user.id,
            )
            created.append(s)
        await self.session.flush()
        return [self._scenario_view(s) for s in created]

    async def list_scenarios(self, org_id: str, user: User) -> list[dict]:
        m = await self.member_repo.get_membership(org_id, user.id)
        self._check_org_access(m)
        result = await self.session.execute(
            select(DemoScenario)
            .where(DemoScenario.organization_id == org_id)
            .order_by(DemoScenario.scenario_type)
        )
        scenarios = list(result.scalars().all())
        return [self._scenario_view(s) for s in scenarios]

    async def get_scenario(self, org_id: str, scenario_id: str, user: User) -> dict:
        m = await self.member_repo.get_membership(org_id, user.id)
        self._check_org_access(m)
        s = await self._get_scenario(scenario_id, org_id)
        return self._scenario_view(s)

    async def run_scenario(
        self, org_id: str, scenario_id: str, user: User
    ) -> dict:
        m = await self.member_repo.get_membership(org_id, user.id)
        self._check_org_access(m)
        scenario = await self._get_scenario(scenario_id, org_id)

        run = await self._add(
            DemoScenarioRun,
            organization_id=org_id,
            scenario_id=scenario.id,
            is_replay=False,
            status=ScenarioRunStatus.RUNNING.value,
            total_steps=len(scenario.flow_steps),
            created_by=user.id,
        )

        result = await self._execute_scenario(org_id, user, scenario, run)

        await self.audit_repo.log(
            action="demo_scenario.run",
            resource_type="demo_scenario_run",
            resource_id=run.id,
            user_id=user.id,
        )
        return result

    async def replay_scenario(
        self, org_id: str, scenario_id: str, run_id: str | None, user: User
    ) -> dict:
        """Replay: re-execute producing the same logical outputs (new row IDs)."""
        m = await self.member_repo.get_membership(org_id, user.id)
        self._check_org_access(m)
        scenario = await self._get_scenario(scenario_id, org_id)

        # Find run to replay from (latest completed if not specified)
        if run_id:
            source_run = await self._get_run(run_id, org_id)
        else:
            r = await self.session.execute(
                select(DemoScenarioRun)
                .where(
                    DemoScenarioRun.scenario_id == scenario.id,
                    DemoScenarioRun.organization_id == org_id,
                    DemoScenarioRun.status == ScenarioRunStatus.COMPLETED.value,
                )
                .order_by(DemoScenarioRun.created_at.desc())
                .limit(1)
            )
            source_run = r.scalar_one_or_none()

        replay = await self._add(
            DemoScenarioRun,
            organization_id=org_id,
            scenario_id=scenario.id,
            replayed_from_id=source_run.id if source_run else None,
            is_replay=True,
            status=ScenarioRunStatus.RUNNING.value,
            total_steps=len(scenario.flow_steps),
            created_by=user.id,
        )
        result = await self._execute_scenario(org_id, user, scenario, replay)
        await self.audit_repo.log(
            action="demo_scenario.replay",
            resource_type="demo_scenario_run",
            resource_id=replay.id,
            user_id=user.id,
        )
        return result

    async def reset_scenario(self, org_id: str, scenario_id: str, user: User) -> dict:
        """Delete all runs for a scenario; reset run_count to 0."""
        m = await self.member_repo.get_membership(org_id, user.id)
        self._check_org_access(m)
        scenario = await self._get_scenario(scenario_id, org_id)

        await self.session.execute(
            delete(DemoScenarioRun).where(
                DemoScenarioRun.scenario_id == scenario.id,
                DemoScenarioRun.organization_id == org_id,
            )
        )
        scenario.run_count = 0
        scenario.last_run_id = None
        scenario.status = ScenarioStatus.AVAILABLE.value
        await self.session.flush()
        await self.audit_repo.log(
            action="demo_scenario.reset",
            resource_type="demo_scenario",
            resource_id=scenario_id,
            user_id=user.id,
        )
        return self._scenario_view(scenario)

    async def list_runs(self, org_id: str, user: User, scenario_id: str | None = None) -> list[dict]:
        m = await self.member_repo.get_membership(org_id, user.id)
        self._check_org_access(m)
        filters = [DemoScenarioRun.organization_id == org_id]
        if scenario_id:
            filters.append(DemoScenarioRun.scenario_id == scenario_id)
        result = await self.session.execute(
            select(DemoScenarioRun)
            .where(*filters)
            .order_by(DemoScenarioRun.created_at.desc())
            .limit(100)
        )
        return [self._run_view(r) for r in result.scalars().all()]

    # ------------------------------------------------------------------ #
    # Execution engine
    # ------------------------------------------------------------------ #
    async def _execute_scenario(
        self,
        org_id: str,
        user: User,
        scenario: DemoScenario,
        run: DemoScenarioRun,
    ) -> dict:
        t = ScenarioType(scenario.scenario_type)
        dispatch = {
            ScenarioType.CHECKOUT_OUTAGE: self._run_checkout_outage,
            ScenarioType.DATABASE_LATENCY: self._run_database_latency,
            ScenarioType.MEMORY_LEAK: self._run_memory_leak,
            ScenarioType.BAD_DEPLOYMENT: self._run_bad_deployment,
            ScenarioType.COST_EXPLOSION: self._run_cost_explosion,
        }
        handler = dispatch.get(t, self._run_generic)
        step_log, events, incident_ids, alert_ids = await handler(org_id, user, scenario)

        run.status = ScenarioRunStatus.COMPLETED.value
        run.step_log = step_log
        run.generated_events = events
        run.incident_ids = incident_ids
        run.alert_ids = alert_ids
        run.completed_steps = len(step_log)
        run.duration_seconds = float(len(step_log) * 0.15)
        await self.session.flush()

        scenario.run_count = (scenario.run_count or 0) + 1
        scenario.last_run_id = run.id
        scenario.status = ScenarioStatus.COMPLETED.value
        await self.session.flush()

        return self._run_view(run)

    # ---- scenario implementations ----------------------------------------

    async def _run_checkout_outage(self, org_id, user, scenario):
        now = _now()
        uid = user.id
        step_log, events, incident_ids, alert_ids = [], [], [], []

        def _step(n, summary):
            step_log.append({"step": n, "status": "COMPLETED",
                              "summary": summary, "timestamp": now.isoformat()})

        # Step 1-3: deployment + K8s
        _step(1, "GitHub deployment checkout-service v2.3.1 recorded.")
        _step(2, "Kubernetes rollout initiated; liveness probe failures detected.")
        _step(3, "CrashLoopBackOff confirmed on 2/3 new pods.")

        # Step 4: alert
        alert = await self._add(
            MonitoringAlert,
            organization_id=org_id,
            provider="PROMETHEUS",
            alert_id=f"sc-alert-{uuid.uuid4().hex[:8]}",
            alert_name="checkout-service HTTP 5xx > 5%",
            severity="CRITICAL",
            status="RESOLVED",
            service="checkout-service",
            environment="production",
            description="Error rate 12% on checkout-service after v2.3.1 deploy.",
            first_seen_at=now - timedelta(minutes=40),
            last_seen_at=now - timedelta(minutes=5),
            occurrence_count=3,
        )
        alert_ids.append(alert.id)
        _step(4, f"CRITICAL alert fired (id={alert.id[:8]}).")

        # Step 5-6: incident + timeline
        inv = await self._add(
            IncidentInvestigation,
            organization_id=org_id,
            title="Checkout 5xx spike — v2.3.1 regression",
            prompt="Investigate checkout-service CRITICAL alert.",
            status="COMPLETED",
            source="MONITORING",
            severity="CRITICAL",
            summary="v2.3.1 introduced null payment-token path that caused 500s on guest checkout.",
            root_cause="Null payment-token path in guest checkout — introduced in v2.3.1.",
            recommendations="Roll back to v2.2.9; validate guest checkout flow in staging.",
            confidence_score=94,
            suspected_trigger="Deploy checkout-service v2.3.1",
            suspected_provider="GITHUB",
            created_by=uid,
            created_at=now - timedelta(minutes=38),
        )
        incident_ids.append(inv.id)
        # Link alert to incident
        alert.incident_id = inv.id
        await self.session.flush()
        _step(5, f"Incident investigation opened (id={inv.id[:8]}).")

        for so, (prov, action) in enumerate([
            ("PROMETHEUS", "Query error-rate & latency metrics"),
            ("KUBERNETES", "Inspect pod restarts and CrashLoopBackOff reason"),
            ("GITHUB", "Correlate recent deployments with v2.3.1 change set"),
            ("DATADOG", "Review APM traces for null pointer exceptions"),
        ], start=1):
            await self._add(
                IncidentInvestigationStep,
                investigation_id=inv.id, organization_id=org_id,
                step_order=so, tool_provider=prov, action=action, status="COMPLETED",
                result_summary=f"{action}: evidence collected.",
                execution_time_ms=350 + so * 100,
            )
        for etype, title, ts, sev_e in [
            ("DEPLOYMENT", "checkout-service v2.3.1 deployed", now - timedelta(minutes=42), "INFO"),
            ("ALERT", "5xx rate > 5%", now - timedelta(minutes=40), "CRITICAL"),
            ("METRIC", "Error rate spiked to 12%", now - timedelta(minutes=38), "WARNING"),
            ("INCIDENT", "Incident mitigated — rolled back", now - timedelta(minutes=5), "INFO"),
        ]:
            await self._add(
                IncidentTimelineEvent,
                investigation_id=inv.id, organization_id=org_id,
                provider="GITHUB" if etype == "DEPLOYMENT" else "PROMETHEUS",
                event_type=etype, event_timestamp=ts,
                title=title, description=f"{title} for checkout-service.", severity=sev_e,
                event_metadata={"service": "checkout-service"},
            )
        _step(6, "Timeline built with 4 correlated events.")

        # Change event
        await self._add(
            DeploymentChangeEvent,
            investigation_id=inv.id, organization_id=org_id,
            provider="GITHUB", change_type="DEPLOYMENT",
            change_timestamp=now - timedelta(minutes=42),
            actor="ci-bot", title="Deploy checkout-service v2.3.1",
            description="PR #2105 merged: null payment-token path regression.",
            version="v2.3.1", event_metadata={"service": "checkout-service"},
        )
        _step(7, "Root cause confirmed: null payment-token path in v2.3.1.")

        # Recommendations
        recs = [
            ("Deployment", "Roll back checkout-service to v2.2.9", "MEDIUM", 94, 8),
            ("Monitoring", "Add null-check assertion in staging CI pipeline", "LOW", 80, 30),
        ]
        rec_rows = []
        for ro, (rtype, rtitle, risk, conf, mins) in enumerate(recs, start=1):
            r = await self._add(
                IncidentRecommendation,
                investigation_id=inv.id, organization_id=org_id,
                recommendation_type=rtype, title=rtitle,
                description=f"{rtitle}. ~{mins} min recovery.",
                risk_level=risk, confidence_score=conf,
                estimated_recovery_minutes=mins, recommendation_order=ro,
                event_metadata={"service": "checkout-service"},
            )
            rec_rows.append(r)
        _step(8, "2 recommendations generated (rollback + CI assertion).")

        # Remediation action
        action_row = await self._add(
            IncidentRemediationAction,
            organization_id=org_id, investigation_id=inv.id,
            recommendation_id=rec_rows[0].id,
            action_type="ROLLBACK", provider="KUBERNETES",
            title="Roll back checkout-service to v2.2.9",
            description="Rollback to last healthy revision v2.2.9.",
            risk_level="MEDIUM", environment="production",
            application="checkout-service",
            target_config={"strategy": "rollback", "version": "v2.2.9"},
            status="APPROVED", action_metadata={"demo": True, "scenario": scenario.id},
        )
        await self._add(
            IncidentRemediationApproval,
            organization_id=org_id, action_id=action_row.id,
            status="APPROVED", approver_user_id=uid,
            comments="Approved in demo scenario.",
        )
        _step(9, "Rollback approved and executed; error rate back to baseline.")

        # War room
        room = await self._add(
            WarRoom,
            organization_id=org_id, incident_id=inv.id,
            title="War Room — Checkout Outage",
            status="CLOSED",
            summary="Consensus: v2.3.1 regression. Roll back immediately.",
            consensus_rca="Null payment-token in guest checkout path.",
            remediation_plan=[
                {"step": 1, "action": "Roll back to v2.2.9", "risk": "MEDIUM"},
                {"step": 2, "action": "Validate SLO recovery", "risk": "LOW"},
            ],
            confidence_score=94,
            participating_agents=["SRE", "KUBERNETES", "GITHUB", "DATABASE"],
            requires_approval=False, message_count=5,
            created_by=uid,
        )
        for seq, (agent, mtype, content) in enumerate([
            ("SRE", "FINDING", "Error rate spiked 2 min after v2.3.1 deploy."),
            ("GITHUB", "FINDING", "Change set includes guest checkout path mutation."),
            ("KUBERNETES", "FINDING", "CrashLoopBackOff on new pods; old pods healthy."),
            ("DATABASE", "CHALLENGE", "No DB anomalies — issue is application-level."),
            ("SRE", "CONSENSUS", "Rollback to v2.2.9 — confidence 94%."),
        ], start=1):
            await self._add(
                WarRoomMessage,
                war_room_id=room.id, organization_id=org_id,
                agent=agent, message_type=mtype, content=content,
                confidence=94 if mtype == "CONSENSUS" else None,
                sequence=seq,
            )
        room.message_count = 5
        await self.session.flush()

        # Postmortem
        await self._add(
            IncidentPostmortem,
            organization_id=org_id, investigation_id=inv.id,
            title="Postmortem — Checkout Outage (v2.3.1)",
            status="GENERATED", severity="CRITICAL", source="MONITORING",
            confidence_score=94, version=1, generated_by="AUTO",
            executive_summary="v2.3.1 introduced a null payment-token regression; "
                               "38-minute impact on checkout; resolved via rollback.",
            impact_analysis="~12% of checkout orders failed for 38 minutes.",
            timeline_summary="Deploy → alert → investigation → rollback → recovery.",
            root_cause="Null payment-token path in guest checkout (v2.3.1).",
            triggering_change="Deploy checkout-service v2.3.1",
            resolution="Rolled back to v2.2.9; error rate normalised in < 6 min.",
            lessons_learned="Require staging guest-checkout smoke test before prod deploy.",
            action_items=[
                {"title": "Add guest-checkout smoke test in CI", "owner": "Release Manager",
                 "status": "OPEN", "source": "postmortem", "risk_level": "LOW"},
                {"title": "Enable canary rollout for checkout-service",
                 "owner": "SRE Lead", "status": "OPEN", "source": "postmortem", "risk_level": "LOW"},
            ],
            content_markdown=(
                "# Postmortem — Checkout Outage (v2.3.1)\n\n"
                "**Root cause:** Null payment-token regression in v2.3.1.\n\n"
                "**Resolution:** Rollback to v2.2.9.\n"
            ),
            created_by=uid,
        )
        _step(10, "Postmortem generated with 2 action items.")
        events.extend([
            {"type": "alert", "id": alert.id, "name": "checkout 5xx CRITICAL"},
            {"type": "incident", "id": inv.id, "title": inv.title},
        ])
        return step_log, events, incident_ids, alert_ids

    async def _run_database_latency(self, org_id, user, scenario):
        now = _now()
        uid = user.id
        step_log, events, incident_ids, alert_ids = [], [], [], []

        def _step(n, s):
            step_log.append({"step": n, "status": "COMPLETED",
                              "summary": s, "timestamp": now.isoformat()})

        alert = await self._add(
            MonitoringAlert,
            organization_id=org_id,
            provider="PROMETHEUS",
            alert_id=f"sc-db-{uuid.uuid4().hex[:8]}",
            alert_name="orders-db p95 latency > 500 ms",
            severity="HIGH",
            status="RESOLVED",
            service="orders-db",
            environment="production",
            description="p95 query latency on orders-db has exceeded 500 ms for 5 min.",
            first_seen_at=now - timedelta(hours=3),
            last_seen_at=now - timedelta(hours=1),
            occurrence_count=2,
        )
        alert_ids.append(alert.id)
        _step(1, "Slow query metrics detected on orders-db (p95 > 500 ms).")
        _step(2, f"HIGH alert fired (id={alert.id[:8]}).")
        _step(3, "Checkout SLO error-budget burn rate at 4× in 1-hour window.")

        # Capacity warning
        await self._add(
            CapacityForecast,
            organization_id=org_id,
            cluster="prod-us-east",
            service="orders-db",
            environment="production",
            resource_type="CPU",
            unit="cores",
            current_usage=28.8,
            capacity=32.0,
            current_utilization=90.0,
            growth_rate_per_day=0.5,
            trend="GROWING",
            forecast_7d=32.0,
            forecast_30d=47.0,
            forecast_90d=62.0,
            saturation_threshold=90.0,
            saturation_date=now + timedelta(hours=48),
            status="CRITICAL",
            recommendation_action="ADD_NODES",
            recommendation="Urgent: scale orders-db before projected saturation.",
            current_cost=345.6,
            projected_cost=564.0,
            delta_cost=218.4,
            confidence=0.92,
            data_points=7,
            details={"service": "orders-db", "scenario": scenario.id},
            created_by=uid,
        )
        _step(4, "CRITICAL capacity warning: CPU saturation in 48 h.")

        inv = await self._add(
            IncidentInvestigation,
            organization_id=org_id,
            title="orders-db latency surge — missing index",
            prompt="Investigate orders-db HIGH latency alert.",
            status="COMPLETED",
            source="MONITORING",
            severity="HIGH",
            summary="Missing composite index (order_id, status) caused full-table scans.",
            root_cause="Missing composite index on orders table — introduced by schema migration.",
            recommendations="Add index; scale read replica; enable query result cache.",
            confidence_score=91,
            suspected_trigger="Schema migration removing composite index",
            suspected_provider="GITHUB",
            created_by=uid,
            created_at=now - timedelta(hours=2, minutes=30),
        )
        incident_ids.append(inv.id)
        alert.incident_id = inv.id
        await self.session.flush()
        _step(5, f"Investigation opened (id={inv.id[:8]}).")
        _step(6, "Root cause: missing composite index (order_id, status).")

        for ro, (rtype, title, risk, conf, mins) in enumerate([
            ("Database", "Add composite index (order_id, status)", "LOW", 91, 15),
            ("Scaling", "Scale read replica to offload analytics queries", "MEDIUM", 80, 30),
            ("Configuration", "Enable query result cache for frequent reads", "LOW", 75, 20),
        ], start=1):
            await self._add(
                IncidentRecommendation,
                investigation_id=inv.id, organization_id=org_id,
                recommendation_type=rtype, title=title,
                description=f"{title} — ~{mins} min to apply.",
                risk_level=risk, confidence_score=conf,
                estimated_recovery_minutes=mins, recommendation_order=ro,
                event_metadata={"service": "orders-db"},
            )
        _step(7, "3 recommendations generated (index + scaling + cache).")
        events.append({"type": "alert", "id": alert.id, "name": "orders-db latency HIGH"})
        events.append({"type": "incident", "id": inv.id, "title": inv.title})
        return step_log, events, incident_ids, alert_ids

    async def _run_memory_leak(self, org_id, user, scenario):
        now = _now()
        uid = user.id
        step_log, events, incident_ids, alert_ids = [], [], [], []

        def _step(n, s):
            step_log.append({"step": n, "status": "COMPLETED",
                              "summary": s, "timestamp": now.isoformat()})

        _step(1, "Memory growth detected: payment-gateway RSS up 3%/h over 6 h.")

        alert_oom = await self._add(
            MonitoringAlert,
            organization_id=org_id,
            provider="KUBERNETES",
            alert_id=f"sc-oom-{uuid.uuid4().hex[:8]}",
            alert_name="payment-gateway OOMKilled",
            severity="HIGH",
            status="FIRING",
            service="payment-gateway",
            environment="production",
            description="payment-gateway pod OOMKilled — 5 restarts in 10 h.",
            first_seen_at=now - timedelta(hours=10),
            last_seen_at=now - timedelta(minutes=30),
            occurrence_count=5,
        )
        alert_ids.append(alert_oom.id)
        _step(2, f"OOM events recorded — 5 OOMKilled events (alert={alert_oom.id[:8]}).")

        alert_restart = await self._add(
            MonitoringAlert,
            organization_id=org_id,
            provider="PROMETHEUS",
            alert_id=f"sc-restart-{uuid.uuid4().hex[:8]}",
            alert_name="payment-gateway restart count > 3",
            severity="WARNING",
            status="FIRING",
            service="payment-gateway",
            environment="production",
            description="Restart count reached 5 — availability SLO at risk.",
            first_seen_at=now - timedelta(hours=8),
            last_seen_at=now - timedelta(minutes=20),
            occurrence_count=5,
        )
        alert_ids.append(alert_restart.id)
        _step(3, "Pod restart alert: restart_count=5 — SLO at risk.")
        _step(4, "Customer impact: payment success rate dropped 1.2%.")

        inv = await self._add(
            IncidentInvestigation,
            organization_id=org_id,
            title="payment-gateway memory leak — connection pool exhaustion",
            prompt="Investigate payment-gateway OOM and restart events.",
            status="COMPLETED",
            source="MONITORING",
            severity="HIGH",
            summary="HTTP client connection pool not closing idle connections — RSS grows unbounded.",
            root_cause="HTTP client (v3.1.0) leaks idle connections; pool exceeds memory limit.",
            recommendations="Patch connection pool; rolling restart; add memory limit.",
            confidence_score=88,
            suspected_trigger="Upgrade payment-gateway to v3.1.0 (HTTP client update)",
            suspected_provider="GITHUB",
            created_by=uid,
            created_at=now - timedelta(hours=6),
        )
        incident_ids.append(inv.id)
        alert_oom.incident_id = inv.id
        await self.session.flush()
        _step(5, f"Investigation opened (id={inv.id[:8]}).")
        _step(6, "Root cause: HTTP client v3.1.0 leaks idle connections.")

        for ro, (rtype, title, risk, conf, mins) in enumerate([
            ("Deployment", "Patch HTTP client to v3.1.1 (connection pool fix)", "MEDIUM", 88, 20),
            ("Configuration", "Set explicit connection pool max_idle=10", "LOW", 82, 5),
            ("Operations", "Rolling restart to recover current pods", "LOW", 95, 3),
        ], start=1):
            await self._add(
                IncidentRecommendation,
                investigation_id=inv.id, organization_id=org_id,
                recommendation_type=rtype, title=title,
                description=f"{title}.", risk_level=risk, confidence_score=conf,
                estimated_recovery_minutes=mins, recommendation_order=ro,
                event_metadata={"service": "payment-gateway"},
            )
        _step(7, "3 remediation recommendations generated.")
        events.extend([
            {"type": "alert", "id": alert_oom.id, "name": "OOMKilled"},
            {"type": "incident", "id": inv.id, "title": inv.title},
        ])
        return step_log, events, incident_ids, alert_ids

    async def _run_bad_deployment(self, org_id, user, scenario):
        now = _now()
        uid = user.id
        step_log, events, incident_ids, alert_ids = [], [], [], []

        def _step(n, s):
            step_log.append({"step": n, "status": "COMPLETED",
                              "summary": s, "timestamp": now.isoformat()})

        _step(1, "PR #2041: 14-file change set targeting checkout-service Tier-1 paths.")

        analysis = await self._add(
            DeploymentSafetyAnalysis,
            organization_id=org_id,
            service="checkout-service",
            environment="production",
            version="v2.4.0-rc1",
            provider="KUBERNETES",
            safety_score=22,
            confidence=0.93,
            readiness="NOT_READY",
            blast_radius="HIGH",
            recommended_strategy="CANARY_10",
            recommended_window="Tue–Thu, 10:00–15:00 (low-traffic window)",
            risk_score=78,
            risk_level="HIGH",
            warnings=[
                "Large change set (14 files) in Tier-1 service",
                "Recent CRITICAL incident on this service (< 7 days)",
                "No staging canary validation completed",
            ],
            details={"scenario": scenario.id, "pr": "#2041"},
            created_by=uid,
            created_at=now - timedelta(hours=1),
        )
        _step(2, f"Deployment safety analysis: risk_score=78/100 HIGH (id={analysis.id[:8]}).")
        _step(3, "Failure probability: 34% regression risk predicted by model.")
        _step(4, "CANARY_10 strategy recommended; approval gate raised.")
        _step(5, "Deployment blocked pending OWNER approval and canary validation.")
        events.append({"type": "deployment_safety", "id": analysis.id, "readiness": "NOT_READY"})
        return step_log, events, incident_ids, alert_ids

    async def _run_cost_explosion(self, org_id, user, scenario):
        now = _now()
        uid = user.id
        step_log, events, incident_ids, alert_ids = [], [], [], []

        def _step(n, s):
            step_log.append({"step": n, "status": "COMPLETED",
                              "summary": s, "timestamp": now.isoformat()})

        _step(1, "3 idle nodes detected (CPU < 10% for 72 h); 4 over-provisioned workloads.")

        forecast = await self._add(
            CapacityForecast,
            organization_id=org_id,
            cluster="prod-us-east",
            service=None,
            environment="production",
            resource_type="COST",
            unit="USD/month",
            current_usage=53000.0,
            capacity=60000.0,
            current_utilization=88.0,
            growth_rate_per_day=650.0,
            trend="GROWING",
            forecast_7d=54550.0,
            forecast_30d=67000.0,
            forecast_90d=110500.0,
            saturation_threshold=90.0,
            saturation_date=now + timedelta(days=30),
            status="WARNING",
            recommendation_action="RIGHT_SIZE",
            recommendation="Right-size 4 over-provisioned deployments; decommission 3 idle nodes.",
            current_cost=53000.0,
            projected_cost=67000.0,
            delta_cost=14000.0,
            confidence=0.91,
            data_points=30,
            details={"scope": "organisation", "scenario": scenario.id},
            created_by=uid,
        )
        _step(2, f"30-day spend forecast: $67 000 without action (id={forecast.id[:8]}).")

        analysis = await self._add(
            CostOptimizationAnalysis,
            organization_id=org_id,
            cluster="prod-us-east",
            service=None,
            environment="production",
            current_cost=53000.0,
            estimated_waste=14820.0,
            potential_savings=12597.0,
            optimized_cost=40403.0,
            annual_savings=151164.0,
            savings_percentage=23.8,
            optimization_score=62,
            optimization_level="NEEDS_IMPROVEMENT",
            forecast_30d=67000.0,
            forecast_90d=110500.0,
            forecast_365d=804000.0,
            idle_count=3,
            overprovisioned_count=4,
            nonprod_count=2,
            confidence=0.91,
            details={"scope": "organisation", "scenario": scenario.id},
            created_by=uid,
        )
        _step(3, f"Waste analysis: $14 820/month recoverable (id={analysis.id[:8]}).")
        _step(4, "Cost optimisation plan: right-size 4 deployments + decommission 3 nodes.")
        _step(5, "Annual savings projection: $151 164/year (optimisation score → 82).")
        events.extend([
            {"type": "cost_analysis", "id": analysis.id, "waste_usd": 14820},
            {"type": "capacity_forecast", "id": forecast.id, "forecast_30d": 67000},
        ])
        return step_log, events, incident_ids, alert_ids

    async def _run_generic(self, org_id, user, scenario):
        now = _now()
        step_log = [
            {"step": i + 1, "status": "COMPLETED",
             "summary": step.get("description", step["name"]),
             "timestamp": now.isoformat()}
            for i, step in enumerate(scenario.flow_steps)
        ]
        return step_log, [], [], []

    # ------------------------------------------------------------------ #
    # Views
    # ------------------------------------------------------------------ #
    @staticmethod
    def _scenario_view(s: DemoScenario) -> dict:
        return {
            "id": s.id,
            "organization_id": s.organization_id,
            "scenario_type": s.scenario_type,
            "name": s.name,
            "description": s.description,
            "template_key": s.template_key,
            "status": s.status,
            "run_count": s.run_count,
            "last_run_id": s.last_run_id,
            "is_builtin": s.is_builtin,
            "flow_steps": s.flow_steps,
            "created_at": s.created_at,
        }

    @staticmethod
    def _run_view(r: DemoScenarioRun) -> dict:
        return {
            "id": r.id,
            "organization_id": r.organization_id,
            "scenario_id": r.scenario_id,
            "is_replay": r.is_replay,
            "replayed_from_id": r.replayed_from_id,
            "status": r.status,
            "total_steps": r.total_steps,
            "completed_steps": r.completed_steps,
            "duration_seconds": r.duration_seconds,
            "incident_ids": r.incident_ids,
            "alert_ids": r.alert_ids,
            "generated_events": r.generated_events,
            "step_log": r.step_log,
            "error_message": r.error_message,
            "created_at": r.created_at,
        }
