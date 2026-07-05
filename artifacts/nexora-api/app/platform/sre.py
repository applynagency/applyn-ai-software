"""Autonomous SRE platform services (Sprint 63B).

Composes existing platform capabilities — AgentRuntime, ExecutionEngine, EventBus,
GraphService, DeploymentRisk, ChangeFailure, Remediation, ExecutiveReporting,
MemoryService — into a unified autonomous SRE layer. No duplicate engines.
"""

from __future__ import annotations

import re
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent_runtime import AgentRuntime
from app.ai.memory import MemoryService
from app.ai.types import LLMMessage, LLMRequest
from app.core.config import settings
from app.core.logging import get_logger
from app.database.base import utcnow
from app.models.ai_platform import AIAgentRun, MemoryScope
from app.models.job import JobType
from app.models.sre import (
    CommanderStatus,
    PredictionType,
    RunbookExecutionStatus,
    SREAIRecommendation,
    SRECommanderRun,
    SRERCAHypothesis,
    SREReliabilityPrediction,
    SRERunbookExecution,
)
from app.platform.config import ConfigService
from app.platform.events import DomainEventType, EventBus, subscribe
from app.platform.execution import ExecutionEngine
from app.repositories.incident import (
    DeploymentChangeEventRepository,
    IncidentInvestigationRepository,
    IncidentTimelineEventRepository,
    MonitoringAlertRepository,
)
from app.repositories.runbook import RunbookRepository
from app.services.graph import GraphService

logger = get_logger(__name__)

_RISK_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
_REMEDIATION_PROVIDERS = (
    "KUBERNETES", "AWS", "AZURE", "GCP", "TERRAFORM", "ANSIBLE", "GITHUB_ACTIONS",
)
_COMMANDER_AGENT = "incident_commander"
_VAR_RE = re.compile(r"\{\{(\w+)\}\}")


def _score_to_level(score: float) -> str:
    if score < 25:
        return "LOW"
    if score < 50:
        return "MEDIUM"
    if score < 75:
        return "HIGH"
    return "CRITICAL"


def _substitute_vars(text: str, variables: dict) -> str:
    def repl(m: re.Match) -> str:
        return str(variables.get(m.group(1), m.group(0)))
    return _VAR_RE.sub(repl, text)


# --------------------------------------------------------------------------- #
# Explainability
# --------------------------------------------------------------------------- #
class ExplainabilityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self, *, organization_id: str, resource_type: str, resource_id: str,
        title: str, confidence: float, evidence: list[dict] | None = None,
        affected_resources: list[dict] | None = None,
        reasoning_summary: str | None = None,
        retrieved_sources: list[dict] | None = None,
        generated_actions: list[dict] | None = None,
    ) -> SREAIRecommendation:
        rec = SREAIRecommendation(
            organization_id=organization_id, resource_type=resource_type,
            resource_id=resource_id, title=title[:300],
            confidence=max(0.0, min(1.0, confidence)),
            evidence=evidence or [], affected_resources=affected_resources or [],
            reasoning_summary=reasoning_summary,
            retrieved_sources=retrieved_sources or [],
            generated_actions=generated_actions or [],
        )
        self.session.add(rec)
        await self.session.flush()
        return rec

    def bundle(self, rec: SREAIRecommendation) -> dict:
        return {
            "id": rec.id, "title": rec.title, "confidence": rec.confidence,
            "evidence": rec.evidence or [], "affected_resources": rec.affected_resources or [],
            "reasoning_summary": rec.reasoning_summary,
            "retrieved_sources": rec.retrieved_sources or [],
            "generated_actions": rec.generated_actions or [],
        }


# --------------------------------------------------------------------------- #
# RCA engine — grounded hypotheses only
# --------------------------------------------------------------------------- #
class RCAEngineService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.incidents = IncidentInvestigationRepository(session)
        self.timeline = IncidentTimelineEventRepository(session)
        self.changes = DeploymentChangeEventRepository(session)
        self.alerts = MonitoringAlertRepository(session)
        self.graph = GraphService(session)
        self.explain = ExplainabilityService(session)

    async def analyze(self, *, organization_id: str, incident_id: str) -> list[SRERCAHypothesis]:
        evidence: list[dict] = []
        sources: list[dict] = []

        inv = await self.incidents.get_for_org(incident_id, organization_id)
        if inv:
            if inv.root_cause:
                evidence.append({
                    "kind": "investigation", "source_id": inv.id,
                    "excerpt": inv.root_cause[:500],
                })
                sources.append({"type": "incident_investigation", "id": inv.id})
            if inv.summary:
                evidence.append({
                    "kind": "summary", "source_id": inv.id,
                    "excerpt": inv.summary[:500],
                })

        for evt in await self.timeline.list_for_investigation(incident_id, organization_id):
            excerpt = (evt.description or evt.title or "")[:300]
            if excerpt:
                evidence.append({
                    "kind": "timeline", "source_id": evt.id, "excerpt": excerpt,
                    "severity": evt.severity,
                })
                sources.append({"type": "timeline_event", "id": evt.id})

        for ch in await self.changes.list_for_investigation(incident_id, organization_id):
            excerpt = f"{ch.change_type}: {ch.title or ch.description or ''}"[:300]
            if excerpt.strip(": "):
                evidence.append({"kind": "deployment_change", "source_id": ch.id, "excerpt": excerpt})
                sources.append({"type": "deployment_change", "id": ch.id})

        alerts, _ = await self.alerts.list_for_org(
            organization_id, status="FIRING", limit=10)
        for alert in alerts:
            excerpt = (alert.alert_name or alert.description or "")[:300]
            if excerpt:
                evidence.append({"kind": "alert", "source_id": alert.id, "excerpt": excerpt})
                sources.append({"type": "monitoring_alert", "id": alert.id})

        if inv and inv.title:
            deps = await self.graph.blast_radius(organization_id, inv.title)
            for dep_key in (deps or [])[:8]:
                evidence.append({
                    "kind": "topology", "source_id": dep_key,
                    "excerpt": f"Blast-radius dependent: {dep_key}",
                })
                sources.append({"type": "graph_node", "id": dep_key})

        if not evidence:
            return []

        hypotheses: list[SRERCAHypothesis] = []
        by_kind: dict[str, list] = {}
        for e in evidence:
            by_kind.setdefault(e["kind"], []).append(e)

        if by_kind.get("deployment_change"):
            conf = min(0.95, 0.5 + 0.1 * len(by_kind["deployment_change"]))
            h = await self._store_hypothesis(
                organization_id, incident_id,
                "Recent deployment or configuration change correlates with incident onset.",
                conf, [e for e in evidence if e["kind"] == "deployment_change"],
                [s for s in sources if s["type"] == "deployment_change"],
            )
            hypotheses.append(h)

        if by_kind.get("alert"):
            conf = min(0.9, 0.4 + 0.08 * len(by_kind["alert"]))
            h = await self._store_hypothesis(
                organization_id, incident_id,
                "Active monitoring alerts indicate ongoing service degradation.",
                conf, [e for e in evidence if e["kind"] == "alert"],
                [s for s in sources if s["type"] == "monitoring_alert"],
            )
            hypotheses.append(h)

        if by_kind.get("topology"):
            h = await self._store_hypothesis(
                organization_id, incident_id,
                "Blast radius may affect dependent services in the topology graph.",
                0.55, [e for e in evidence if e["kind"] == "topology"],
                [s for s in sources if s["type"] == "graph_node"],
            )
            hypotheses.append(h)

        if inv and inv.root_cause and not hypotheses:
            h = await self._store_hypothesis(
                organization_id, incident_id, inv.root_cause,
                0.85, evidence[:5], sources[:5],
            )
            hypotheses.append(h)

        if hypotheses:
            top = hypotheses[0]
            await self.explain.record(
                organization_id=organization_id, resource_type="incident",
                resource_id=incident_id, title="RCA hypothesis",
                confidence=top.confidence, evidence=top.evidence,
                retrieved_sources=top.sources,
                reasoning_summary=top.hypothesis,
            )
        return hypotheses

    async def _store_hypothesis(
        self, org_id: str, incident_id: str, text: str, confidence: float,
        evidence: list, sources: list,
    ) -> SRERCAHypothesis:
        row = SRERCAHypothesis(
            organization_id=org_id, incident_id=incident_id,
            hypothesis=text, confidence=round(confidence, 3),
            evidence=evidence, sources=sources,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_hypotheses(self, *, organization_id: str, incident_id: str) -> list[SRERCAHypothesis]:
        stmt = select(SRERCAHypothesis).where(
            SRERCAHypothesis.organization_id == organization_id,
            SRERCAHypothesis.incident_id == incident_id,
        ).order_by(SRERCAHypothesis.confidence.desc())
        return list((await self.session.execute(stmt)).scalars().all())


# --------------------------------------------------------------------------- #
# Incident Commander — AgentRuntime orchestration
# --------------------------------------------------------------------------- #
class IncidentCommanderService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.runtime = AgentRuntime(session)
        self.rca = RCAEngineService(session)
        self.explain = ExplainabilityService(session)
        self.incidents = IncidentInvestigationRepository(session)

    def _commander_plan(self, incident_summary: str) -> list[dict]:
        return [
            {"id": 0, "description": f"Observe incident: {incident_summary[:200]}",
             "kind": "respond"},
            {"id": 1, "description": "Build investigation plan from correlated signals",
             "kind": "respond"},
            {"id": 2, "description": "Assign investigation steps to AI agents",
             "kind": "respond"},
            {"id": 3, "description": "Request human approval before remediation",
             "kind": "approval"},
            {"id": 4, "description": "Summarize findings and recommend remediation",
             "kind": "respond"},
            {"id": 5, "description": "Draft postmortem outline from investigation",
             "kind": "respond"},
        ]

    async def start(
        self, *, organization_id: str, incident_id: str, user_id: str | None = None,
    ) -> SRECommanderRun:
        inv = await self.incidents.get_for_org(incident_id, organization_id)
        summary = (inv.summary if inv else None) or f"Incident {incident_id}"
        plan = self._commander_plan(summary)
        hypotheses = await self.rca.analyze(organization_id=organization_id, incident_id=incident_id)

        agent_run = await self.runtime.start(
            organization_id=organization_id, agent_key=_COMMANDER_AGENT,
            goal=f"Command incident {incident_id}: investigate, coordinate, recommend remediation",
            user_id=user_id, steps=plan,
        )
        commander = SRECommanderRun(
            organization_id=organization_id, incident_id=incident_id,
            agent_run_id=agent_run.id, status=CommanderStatus.INVESTIGATING.value,
            investigation_plan=plan,
            findings_summary=hypotheses[0].hypothesis if hypotheses else None,
            meta={"hypothesis_count": len(hypotheses)},
        )
        self.session.add(commander)
        await self.session.flush()

        agent_run = await self.runtime.run_to_completion(organization_id, agent_run.id)
        if agent_run.status == "WAITING_APPROVAL":
            commander.status = CommanderStatus.AWAITING_APPROVAL.value
        elif agent_run.status == "COMPLETED":
            commander.status = CommanderStatus.COMPLETED.value
            commander.findings_summary = (
                (agent_run.result or {}).get("summary", {}).get("text")
                if isinstance((agent_run.result or {}).get("summary"), dict)
                else commander.findings_summary
            )
        else:
            commander.status = CommanderStatus.FAILED.value if agent_run.status == "FAILED" else commander.status

        await self.explain.record(
            organization_id=organization_id, resource_type="incident",
            resource_id=incident_id, title="Incident commander summary",
            confidence=0.8 if hypotheses else 0.5,
            evidence=[{"kind": "commander", "agent_run_id": agent_run.id}],
            reasoning_summary=commander.findings_summary,
            generated_actions=[{"type": "approve_remediation", "required": True}],
        )
        await self.session.flush()
        return commander

    async def get(self, commander_id: str, *, organization_id: str) -> SRECommanderRun | None:
        row = await self.session.get(SRECommanderRun, commander_id)
        if row is None or row.organization_id != organization_id:
            return None
        return row

    async def list_active(self, *, organization_id: str, limit: int = 20) -> list[SRECommanderRun]:
        stmt = select(SRECommanderRun).where(
            SRECommanderRun.organization_id == organization_id,
            SRECommanderRun.status.notin_([
                CommanderStatus.COMPLETED.value, CommanderStatus.FAILED.value,
            ]),
        ).order_by(SRECommanderRun.created_at.desc()).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def approve(self, commander_id: str, *, organization_id: str,
                      user_id: str | None = None) -> SRECommanderRun | None:
        commander = await self.get(commander_id, organization_id=organization_id)
        if commander is None or not commander.agent_run_id:
            return None
        await self.runtime.approve(organization_id, commander.agent_run_id, actor_user_id=user_id)
        commander.status = CommanderStatus.SUMMARIZING.value
        run = await self.runtime.run_to_completion(organization_id, commander.agent_run_id)
        commander.status = (
            CommanderStatus.COMPLETED.value if run.status == "COMPLETED"
            else CommanderStatus.FAILED.value
        )
        await self.session.flush()
        return commander


# --------------------------------------------------------------------------- #
# Executable runbooks — ExecutionEngine
# --------------------------------------------------------------------------- #
class ExecutableRunbookService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.runbooks = RunbookRepository(session)
        self.engine = ExecutionEngine(session)
        self.gateway = AgentRuntime(session).gateway

    def _build_steps(self, runbook, variables: dict) -> list[dict]:
        steps: list[dict] = []
        for i, raw in enumerate(runbook.investigation_steps or []):
            steps.append({"index": i, "kind": "action", "text": _substitute_vars(str(raw), variables)})
        for i, raw in enumerate(runbook.validation_steps or []):
            steps.append({"index": len(steps), "kind": "condition",
                          "text": _substitute_vars(str(raw), variables)})
        for i, raw in enumerate(runbook.rollback_steps or []):
            steps.append({"index": len(steps), "kind": "rollback",
                          "text": _substitute_vars(str(raw), variables)})
        steps.append({"index": len(steps), "kind": "approval",
                      "text": "Approve remediation steps before execution"})
        steps.append({"index": len(steps), "kind": "checkpoint", "text": "Pre-execution checkpoint"})
        return steps

    async def execute(
        self, *, organization_id: str, runbook_id: str,
        variables: dict | None = None, user_id: str | None = None,
    ) -> SRERunbookExecution:
        runbook = await self.runbooks.get_for_org(runbook_id, organization_id)
        if runbook is None:
            raise ValueError("runbook not found")
        vars_ = variables or {}
        steps = self._build_steps(runbook, vars_)
        job = await self.engine.submit(
            task_name="sre_runbook_noop", job_type=JobType.CRON_MONITORING,
            organization_id=organization_id, user_id=user_id,
            params={"runbook_id": runbook_id},
        )
        execution = SRERunbookExecution(
            organization_id=organization_id, runbook_id=runbook_id,
            job_id=job["id"], status=RunbookExecutionStatus.RUNNING.value,
            variables=vars_, steps=steps, checkpoints=[],
        )
        self.session.add(execution)
        await self.session.flush()

        checkpoints: list[dict] = []
        for step in steps:
            kind = step.get("kind", "action")
            if kind == "approval":
                execution.status = RunbookExecutionStatus.WAITING_APPROVAL.value
                execution.current_step = step["index"]
                execution.checkpoints = checkpoints
                await self.session.flush()
                return execution
            if kind == "ai_decision":
                req = LLMRequest(
                    messages=[LLMMessage(role="user", content=step["text"])],
                    system="Decide the next runbook step. Ground answer in the step text only.",
                    feature="sre:runbook", organization_id=organization_id, temperature=0.1,
                )
                resp = await self.gateway.complete(req)
                output = resp.text
            elif kind == "condition":
                output = {"passed": True, "note": step["text"]}
            else:
                output = {"executed": step["text"], "simulated": True}
            cp = await self.engine.checkpoint(
                job["id"], label=kind, state={"step": step, "output": output},
                organization_id=organization_id,
            )
            checkpoints.append({"step": step["index"], "kind": kind, "checkpoint_id": cp.id})
            execution.current_step = step["index"] + 1

        execution.status = RunbookExecutionStatus.COMPLETED.value
        execution.checkpoints = checkpoints
        await self.session.flush()
        return execution

    async def approve_execution(
        self, execution_id: str, *, organization_id: str, user_id: str | None = None,
    ) -> SRERunbookExecution | None:
        ex = await self.session.get(SRERunbookExecution, execution_id)
        if ex is None or ex.organization_id != organization_id:
            return None
        if ex.status != RunbookExecutionStatus.WAITING_APPROVAL.value:
            return ex
        remaining = [s for s in (ex.steps or []) if s["index"] > ex.current_step]
        checkpoints = list(ex.checkpoints or [])
        for step in remaining:
            if step.get("kind") == "checkpoint":
                cp = await self.engine.checkpoint(
                    ex.job_id, label="post-approval", state={"step": step},
                    organization_id=organization_id,
                )
                checkpoints.append({"step": step["index"], "checkpoint_id": cp.id})
        ex.status = RunbookExecutionStatus.COMPLETED.value
        ex.checkpoints = checkpoints
        await self.session.flush()
        return ex


# --------------------------------------------------------------------------- #
# Remediation workflows — approval-gated
# --------------------------------------------------------------------------- #
class RemediationWorkflowService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.config = ConfigService(session)

    async def _auto_approved(self, organization_id: str) -> bool:
        val = await self.config.get(
            "sre.auto_approve_remediation", organization_id=organization_id, default=False)
        return bool(val)

    async def create_workflow(
        self, *, organization_id: str, incident_id: str, actions: list[dict],
        user_id: str | None = None,
    ) -> dict:
        from app.services.remediation_actions import RemediationActionService

        auto = await self._auto_approved(organization_id)
        svc = RemediationActionService(self.session)
        created = []
        for spec in actions:
            provider = (spec.get("provider") or "KUBERNETES").upper()
            if provider not in _REMEDIATION_PROVIDERS:
                provider = "KUBERNETES"
            action_spec = {
                "action_type": spec.get("action_type", "RESTART_DEPLOYMENT"),
                "provider": provider,
                "title": spec.get("title", "Remediation action"),
                "risk_level": spec.get("risk_level", "HIGH"),
            }
            created.append({**action_spec, "requires_approval": not auto})
        return {
            "incident_id": incident_id, "actions": created,
            "auto_approve": auto, "approval_required": not auto,
        }


# --------------------------------------------------------------------------- #
# Change risk engine
# --------------------------------------------------------------------------- #
class ChangeRiskEngineService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def assess(
        self, user, org_context, *, candidate: dict | None = None,
    ) -> dict:
        from app.schemas.change_failure import ChangeFailureAnalyzeRequest
        from app.services.change_failure import ChangeFailurePredictionService

        svc = ChangeFailurePredictionService(self.session)
        req = ChangeFailureAnalyzeRequest(**(candidate or {}))
        report = await svc.analyze(user, org_context, req)
        level = (report.risk_level or "LOW").upper()
        if level not in _RISK_LEVELS:
            level = _score_to_level(report.failure_probability or 0)
        evidence = [
            {"factor": f.factor, "points": f.points, "detail": f.detail}
            for f in (report.contributing_factors or [])
        ]
        return {
            "risk_level": level,
            "failure_probability": report.failure_probability,
            "evidence": evidence,
            "blast_radius": report.expected_blast_radius,
            "likely_failure_modes": report.likely_failure_modes,
            "mitigation_steps": report.recommended_mitigation_steps,
        }


# --------------------------------------------------------------------------- #
# Predictive reliability
# --------------------------------------------------------------------------- #
class PredictiveReliabilityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.incidents = IncidentInvestigationRepository(session)

    async def predict_all(self, *, organization_id: str, target: str = "organization") -> list[SREReliabilityPrediction]:
        predictions = []
        for ptype in PredictionType:
            pred = await self._predict_one(organization_id, ptype.value, target)
            if pred:
                predictions.append(pred)
        return predictions

    async def _predict_one(
        self, organization_id: str, prediction_type: str, target: str,
    ) -> SREReliabilityPrediction | None:
        evidence: list[dict] = []
        score = 0.0
        explanation = ""

        rows, _ = await self.incidents.list_for_org(organization_id, limit=30)
        recent = rows
        open_count = sum(1 for i in recent if (i.status or "").upper() in ("RUNNING", "OPEN"))
        incident_count = len(recent)

        if prediction_type == PredictionType.INCIDENT_PROBABILITY.value:
            score = min(100, open_count * 15 + incident_count * 3)
            explanation = f"{open_count} open and {incident_count} recent incidents in lookback window."
            evidence.append({"metric": "open_incidents", "value": open_count})
            evidence.append({"metric": "recent_incidents", "value": incident_count})

        elif prediction_type == PredictionType.RECURRING_INCIDENT.value:
            services: dict[str, int] = {}
            for inv in recent:
                svc_name = inv.title or "unknown"
                services[svc_name] = services.get(svc_name, 0) + 1
            repeat = max(services.values()) if services else 0
            score = min(100, repeat * 20)
            explanation = f"Highest service repeat count: {repeat}."
            evidence.append({"metric": "max_service_repeats", "value": repeat})

        elif prediction_type == PredictionType.DEPLOYMENT_FAILURE.value:
            from app.models.deployment import DeploymentStatus
            from app.repositories.deployment import DeploymentRunRepository

            runs, _ = await DeploymentRunRepository(self.session).list_by_organization(
                organization_id, limit=20)
            failed = sum(1 for r in runs if r.status in (
                DeploymentStatus.FAILED.value, DeploymentStatus.ROLLED_BACK.value))
            score = min(100, failed * 25)
            explanation = f"{failed} failed/rolled-back deployments in recent history."
            evidence.append({"metric": "failed_deployments", "value": failed})

        elif prediction_type == PredictionType.SLO_BREACH.value:
            score = min(100, open_count * 12)
            explanation = f"{open_count} active investigations may correlate with SLO pressure."
            evidence.append({"metric": "active_investigations", "value": open_count})

        elif prediction_type == PredictionType.CAPACITY_EXHAUSTION.value:
            from app.repositories.capacity import CapacityForecastRepository

            forecasts = await CapacityForecastRepository(self.session).list_recent(
                organization_id)
            at_risk = sum(
                1 for f in forecasts
                if (f.status or "").upper() not in ("HEALTHY", "OK", "")
            )
            score = min(100, at_risk * 30)
            explanation = f"{at_risk} capacity forecasts at elevated risk."
            evidence.append({"metric": "capacity_at_risk", "value": at_risk})

        if not explanation:
            return None

        row = SREReliabilityPrediction(
            organization_id=organization_id, prediction_type=prediction_type,
            target=target, score=round(score, 1),
            risk_level=_score_to_level(score), horizon_hours=24,
            explanation=explanation, evidence=evidence,
            expires_at=utcnow() + timedelta(hours=24),
        )
        self.session.add(row)
        await self.session.flush()
        return row


# --------------------------------------------------------------------------- #
# AI Operations Center
# --------------------------------------------------------------------------- #
class OperationsCenterService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.commander = IncidentCommanderService(session)
        self.predictions = PredictiveReliabilityService(session)
        self.incidents = IncidentInvestigationRepository(session)

    async def dashboard(self, *, organization_id: str, user=None, org_context=None) -> dict:
        rows, _ = await self.incidents.list_for_org(organization_id, limit=10)
        active_incidents = rows
        commander_runs = await self.commander.list_active(organization_id=organization_id)
        preds = await self.predictions.predict_all(organization_id=organization_id)

        health_summary = {}
        deployments = {"recent": 0, "failed": 0}
        try:
            from app.models.deployment import DeploymentStatus
            from app.repositories.deployment import DeploymentRunRepository

            runs, _ = await DeploymentRunRepository(self.session).list_by_organization(
                organization_id, limit=10)
            deployments["recent"] = len(runs)
            deployments["failed"] = sum(
                1 for r in runs if r.status == DeploymentStatus.FAILED.value)
        except Exception:  # noqa: BLE001
            pass

        recommendations = list((await self.session.execute(
            select(SREAIRecommendation).where(
                SREAIRecommendation.organization_id == organization_id,
            ).order_by(SREAIRecommendation.created_at.desc()).limit(10)
        )).scalars().all())

        from app.platform.product import InboxService

        inbox_count = 0
        if user:
            inbox_count = await InboxService(self.session).unread_count(
                organization_id=organization_id, user_id=user.id)

        return {
            "organization_id": organization_id,
            "active_incidents": [
                {"id": i.id, "title": i.title, "status": i.status}
                for i in active_incidents
            ],
            "ai_investigations": [
                {"id": c.id, "incident_id": c.incident_id, "status": c.status}
                for c in commander_runs
            ],
            "deployments": deployments,
            "health": health_summary,
            "predictions": [
                {"type": p.prediction_type, "score": p.score, "level": p.risk_level,
                 "explanation": p.explanation}
                for p in preds
            ],
            "notifications_unread": inbox_count,
            "ai_recommendations": [
                ExplainabilityService(self.session).bundle(r) for r in recommendations
            ],
            "updated_at": utcnow().isoformat(),
        }


# --------------------------------------------------------------------------- #
# Executive AI reports
# --------------------------------------------------------------------------- #
class ExecutiveAIReportService:
    _WINDOW = {"DAILY": 1, "WEEKLY": 7, "MONTHLY": 30}

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def generate(self, user, org_context, *, cadence: str = "WEEKLY") -> dict:
        from app.services.executive_report import ExecutiveReportingService
        from app.services.reliability_dashboard import ReliabilityDashboardService

        organization_id = org_context.requires_organization
        cadence = (cadence or "WEEKLY").upper()
        window = self._WINDOW.get(cadence, 7)

        exec_map = {"DAILY": "WEEKLY", "WEEKLY": "WEEKLY", "MONTHLY": "MONTHLY"}
        exec_svc = ExecutiveReportingService(self.session)
        report = await exec_svc.generate(user, org_context, report_type=exec_map.get(cadence, "WEEKLY"))

        rel_svc = ReliabilityDashboardService(self.session)
        dash = await rel_svc.dashboard(
            user, org_context, scope="organization", scope_value=organization_id,
            window_days=window,
        )

        ai_runs = int((await self.session.execute(
            select(func.count(AIAgentRun.id)).where(
                AIAgentRun.organization_id == organization_id,
                AIAgentRun.created_at >= utcnow() - timedelta(days=window),
            )
        )).scalar() or 0)

        recs = list((await self.session.execute(
            select(SREAIRecommendation).where(
                SREAIRecommendation.organization_id == organization_id,
            ).order_by(SREAIRecommendation.created_at.desc()).limit(5)
        )).scalars().all())

        return {
            "cadence": cadence,
            "window_days": window,
            "reliability_score": dash.reliability_score if hasattr(dash, "reliability_score") else report.reliability_score,
            "executive_summary": report.executive_summary,
            "incidents": report.metrics.get("total_incidents") if report.metrics else None,
            "mttr_minutes": report.metrics.get("mttr_minutes") if report.metrics else None,
            "deployments": report.metrics.get("deployment_success_rate") if report.metrics else None,
            "ai_activity": {"agent_runs": ai_runs},
            "recommendations": [ExplainabilityService(self.session).bundle(r) for r in recs],
            "report_id": report.id,
        }


# --------------------------------------------------------------------------- #
# Knowledge learning — AI Memory
# --------------------------------------------------------------------------- #
class KnowledgeLearningService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.memory = MemoryService(session)
        self.incidents = IncidentInvestigationRepository(session)
        self.rca = RCAEngineService(session)

    async def learn_from_incident(self, *, organization_id: str, incident_id: str) -> list[str]:
        inv = await self.incidents.get_for_org(incident_id, organization_id)
        if inv is None:
            return []
        hypotheses = await self.rca.list_hypotheses(
            organization_id=organization_id, incident_id=incident_id)
        stored: list[str] = []
        parts = [
            f"Incident: {inv.title or incident_id}",
            f"Summary: {inv.summary or ''}",
            f"Root cause: {inv.root_cause or ''}",
        ]
        if hypotheses:
            parts.append(f"Top hypothesis: {hypotheses[0].hypothesis}")
        content = "\n".join(p for p in parts if p.strip())
        entry = await self.memory.remember(
            organization_id=organization_id, scope=MemoryScope.SEMANTIC,
            namespace=f"sre/incidents/{incident_id}",
            content=content[:4000], importance=0.8,
            metadata={"incident_id": incident_id, "title": inv.title},
        )
        stored.append(entry.id)

        if inv.root_cause:
            lesson = await self.memory.remember(
                organization_id=organization_id, scope=MemoryScope.SEMANTIC,
                namespace="sre/lessons",
                content=f"Lesson from {incident_id}: {inv.root_cause}"[:2000],
                importance=0.7,
            )
            stored.append(lesson.id)
        return stored


# --------------------------------------------------------------------------- #
# EventBus — ops center live refresh
# --------------------------------------------------------------------------- #
async def sre_event_handler(session: AsyncSession, event) -> None:
    if not settings.AUTONOMOUS_SRE_ENABLED:
        return
    if event.event_type in (
        DomainEventType.INCIDENT_CREATED.value,
        DomainEventType.DEPLOYMENT_COMPLETED.value,
    ):
        try:
            bus = EventBus(session)
            await bus.publish(
                "SREOpsCenterRefresh", organization_id=event.organization_id,
                payload={"trigger": event.event_type}, dispatch=False,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("sre_ops_refresh_failed", error=str(exc))


if settings.AUTONOMOUS_SRE_ENABLED:
    subscribe("*", sre_event_handler)
