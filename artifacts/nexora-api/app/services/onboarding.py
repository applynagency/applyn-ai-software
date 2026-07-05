"""Sprint 47C - Guided Setup Wizard service.

Orchestrates a 10-step onboarding flow designed to get a customer fully set up
in under 10 minutes. Progress is auto-detected from real platform data (so steps
tick off as the customer connects tools and runs generators) and merged with any
steps explicitly marked complete. State is persisted for resume-later.

SAFETY: read-only orchestration - it inspects existing data and never mutates
infrastructure or executes actions. No secrets are read or stored.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NexoraException, NotFoundError, ValidationError
from app.models.ai_team import AITeam, AITeamAgent, AITeamStatus
from app.models.integration import IntegrationCategory
from app.models.onboarding import OnboardingStatus, OnboardingStep
from app.repositories.audit import AuditLogRepository
from app.repositories.change_failure import ChangeFailurePredictionRepository
from app.repositories.credential import DeploymentCredentialRepository
from app.repositories.deployment import DeploymentRunRepository
from app.repositories.deployment_safety import DeploymentSafetyRepository
from app.repositories.discovery_pipeline import DiscoveryScanRunRepository
from app.repositories.executive_report import ExecutiveReportRepository
from app.repositories.incident import MonitoringAlertRepository
from app.repositories.integration import IntegrationConnectionRepository
from app.repositories.onboarding import OnboardingSessionRepository
from app.repositories.reliability_maturity import ReliabilityAssessmentRepository
from app.repositories.slo import ServiceRepository
from app.schemas.onboarding import (
    OnboardingCompleteResponse,
    OnboardingResponse,
    Recommendation,
    StepInfo,
)
from app.services.graph import GraphService
from app.services.integration_definitions import INTEGRATION_DEFINITIONS
from app.tenancy.permissions import can_read_resources, can_write_resources

logger = structlog.get_logger(__name__)

S = OnboardingStep

# Ordered step metadata (title, description, recommendation action).
STEP_META: list[tuple[str, str, str, str]] = [
    (S.ORGANIZATION_SETUP.value, "Organization Setup",
     "Create your organization and invite your team.",
     "Confirm your organization details under Settings."),
    (S.CONNECT_INFRASTRUCTURE.value, "Connect Infrastructure",
     "Connect AWS, Azure or Kubernetes so we can map your environment.",
     "Connect a cloud or Kubernetes provider in the Integration Marketplace."),
    (S.CONNECT_MONITORING.value, "Connect Monitoring",
     "Connect Datadog, Prometheus, Grafana or New Relic for live signals.",
     "Connect an observability provider in the Integration Marketplace."),
    (S.CONNECT_SOURCE_CONTROL.value, "Connect Source Control",
     "Connect GitHub, GitLab or Bitbucket to correlate deployments.",
     "Connect a source-control provider in the Integration Marketplace."),
    (S.RUN_DISCOVERY.value, "Run Discovery",
     "Automatically discover your services and infrastructure.",
     "Run a discovery from the Infrastructure Discovery page."),
    (S.GENERATE_SERVICE_CATALOG.value, "Generate Service Catalog",
     "Build a catalog of your services from discovered resources.",
     "Run discovery (auto-creates catalog) or add services manually."),
    (S.GENERATE_DEPENDENCY_GRAPH.value, "Generate Dependency Graph",
     "Map dependencies between your services.",
     "Add dependencies or run discovery with relationships to build the graph."),
    (S.GENERATE_RELIABILITY_REPORT.value, "Generate Reliability Report",
     "Produce a reliability maturity / executive reliability report.",
     "Generate a reliability assessment or executive report."),
    (S.GENERATE_DEPLOYMENT_RISK_REPORT.value, "Generate Deployment Risk Report",
     "Analyze deployment/change failure risk.",
     "Run a change-failure prediction or deployment-safety analysis."),
    (S.FINISH.value, "Finish",
     "Review your setup summary and start operating.",
     "Complete onboarding to generate your summary."),
]
STEP_ORDER = [m[0] for m in STEP_META]
_CORE_STEPS = [s for s in STEP_ORDER if s != S.FINISH.value]


def _now() -> datetime:
    return datetime.now(UTC)


class OnboardingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit_repo = AuditLogRepository(session)
        self.repo = OnboardingSessionRepository(session)
        self.conn_repo = IntegrationConnectionRepository(session)
        self.cred_repo = DeploymentCredentialRepository(session)
        self.alert_repo = MonitoringAlertRepository(session)
        self.run_repo = DeploymentRunRepository(session)
        self.discovery_repo = DiscoveryScanRunRepository(session)
        self.service_repo = ServiceRepository(session)
        self.graph = GraphService(session)
        self.exec_repo = ExecutiveReportRepository(session)
        self.maturity_repo = ReliabilityAssessmentRepository(session)
        self.cfp_repo = ChangeFailurePredictionRepository(session)
        self.safety_repo = DeploymentSafetyRepository(session)

    # --------------------------------------------------------------- guards
    def _ensure_read(self, user, org_context) -> None:
        if not user.is_superuser and (not org_context.role or not can_read_resources(org_context.role)):
            raise ForbiddenError()

    def _ensure_write(self, user, org_context) -> None:
        if not user.is_superuser and (not org_context.role or not can_write_resources(org_context.role)):
            raise ForbiddenError()

    # --------------------------------------------------------------- detect
    async def _detect(self, organization_id: str) -> dict[str, bool]:
        """Auto-detect which steps are satisfied by existing platform data."""
        connections = await self.conn_repo.list_for_org(organization_id)
        conn_categories = {
            INTEGRATION_DEFINITIONS.get(c.integration_key, {}).get("category")
            for c in connections
        }
        conn_keys = {c.integration_key for c in connections}

        creds, _ = await self.cred_repo.list_for_org(organization_id, limit=500)
        cred_providers = {c.provider for c in creds}
        cloud_creds = bool(cred_providers & {"AWS", "AZURE", "KUBERNETES", "VM"})

        alerts, _ = await self.alert_repo.list_for_org(organization_id, limit=50)
        runs, _ = await self.run_repo.list_by_organization(organization_id, limit=50)

        discoveries = await self.discovery_repo.list_for_org(organization_id, limit=1)
        services = await self.service_repo.list_for_org(organization_id)
        deps = await self.graph.list_service_edges(organization_id)
        exec_reports = await self.exec_repo.list_for_org(organization_id, limit=1)
        assessments = await self.maturity_repo.list_for_org(organization_id, limit=1)
        cfps = await self.cfp_repo.list_for_org(organization_id, limit=1)
        safety = await self.safety_repo.list_for_org(organization_id, limit=1)

        return {
            S.ORGANIZATION_SETUP.value: True,  # an org always exists in this context
            S.CONNECT_INFRASTRUCTURE.value: (
                IntegrationCategory.CLOUD.value in conn_categories
                or IntegrationCategory.ORCHESTRATION.value in conn_categories
                or cloud_creds
            ),
            S.CONNECT_MONITORING.value: (
                IntegrationCategory.OBSERVABILITY.value in conn_categories or bool(alerts)
            ),
            S.CONNECT_SOURCE_CONTROL.value: (
                bool(conn_keys & {"GITHUB", "GITLAB", "BITBUCKET"}) or bool(runs)
            ),
            S.RUN_DISCOVERY.value: bool(discoveries),
            S.GENERATE_SERVICE_CATALOG.value: bool(services),
            S.GENERATE_DEPENDENCY_GRAPH.value: bool(deps),
            S.GENERATE_RELIABILITY_REPORT.value: bool(exec_reports) or bool(assessments),
            S.GENERATE_DEPLOYMENT_RISK_REPORT.value: bool(cfps) or bool(safety),
            S.FINISH.value: False,  # only via explicit complete
        }

    # --------------------------------------------------------------- compute
    def _build_response(self, sess, detected: dict[str, bool]) -> OnboardingResponse:
        explicit = set(sess.completed_steps or [])
        completed = {s for s in STEP_ORDER if detected.get(s) or s in explicit}
        if sess.status == OnboardingStatus.COMPLETED.value:
            completed.add(S.FINISH.value)

        steps: list[StepInfo] = []
        for idx, (key, title, desc, _action) in enumerate(STEP_META):
            steps.append(StepInfo(
                key=key, order=idx + 1, title=title, description=desc,
                completed=key in completed,
                auto_detected=bool(detected.get(key)) and key not in explicit,
            ))

        progress = round(len(completed & set(STEP_ORDER)) / len(STEP_ORDER) * 100)
        missing = [s for s in STEP_ORDER if s not in completed]
        current = missing[0] if missing else S.FINISH.value

        recs = [
            Recommendation(step=key, title=title, action=action)
            for (key, title, _desc, action) in STEP_META
            if key not in completed and key != S.FINISH.value
        ]

        return OnboardingResponse(
            id=sess.id, organization_id=sess.organization_id, status=sess.status,
            current_step=current, progress_percent=progress, steps=steps,
            completed_steps=sorted(completed, key=lambda s: STEP_ORDER.index(s)),
            missing_steps=missing, recommendations=recs,
            summary=sess.summary, created_at=sess.created_at,
        )

    async def _persist_progress(self, sess, detected, *, completed_override=None):
        explicit = set(sess.completed_steps or [])
        completed = {s for s in STEP_ORDER if detected.get(s) or s in explicit}
        if completed_override:
            completed |= completed_override
        progress = round(len(completed & set(STEP_ORDER)) / len(STEP_ORDER) * 100)
        missing = [s for s in STEP_ORDER if s not in completed]
        current = missing[0] if missing else S.FINISH.value
        await self.repo.update(sess, progress_percent=progress, current_step=current)

    # --------------------------------------------------------------- public
    async def start(self, user, org_context, req) -> OnboardingResponse:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)

        sess = None
        if not req.force_new:
            sess = await self.repo.latest_in_progress(organization_id)
        if sess is None:
            sess = await self.repo.create(
                organization_id=organization_id,
                status=OnboardingStatus.IN_PROGRESS.value,
                current_step=S.ORGANIZATION_SETUP.value,
                completed_steps=[S.ORGANIZATION_SETUP.value],
                step_data={"organization_name": req.organization_name} if req.organization_name else {},
                progress_percent=0, recommendations=[],
                created_by=user.id,
            )
            await self.session.flush()
            await self.audit_repo.log(
                action="onboarding_started", resource_type="onboarding_session",
                resource_id=sess.id, user_id=user.id,
                details={"organization_id": organization_id},
            )

        detected = await self._detect(organization_id)
        await self._persist_progress(sess, detected)
        await self.session.commit()
        return self._build_response(sess, detected)

    async def get(self, user, org_context, session_id: str) -> OnboardingResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        sess = await self.repo.get_for_org(session_id, organization_id)
        if sess is None:
            raise NexoraException("Onboarding session not found.", status_code=404)
        detected = await self._detect(organization_id)
        await self._persist_progress(sess, detected)
        await self.session.commit()
        return self._build_response(sess, detected)

    async def step(self, user, org_context, session_id: str, req) -> OnboardingResponse:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        sess = await self.repo.get_for_org(session_id, organization_id)
        if sess is None:
            raise NexoraException("Onboarding session not found.", status_code=404)
        step = (req.step or "").upper()
        if step not in STEP_ORDER:
            raise ValidationError(f"Unknown onboarding step: {req.step}")

        explicit = set(sess.completed_steps or [])
        if req.completed:
            explicit.add(step)
        else:
            explicit.discard(step)
        step_data = dict(sess.step_data or {})
        if req.data:
            step_data[step] = req.data

        sess = await self.repo.update(
            sess, completed_steps=sorted(explicit, key=lambda s: STEP_ORDER.index(s)),
            step_data=step_data,
        )
        detected = await self._detect(organization_id)
        await self._persist_progress(sess, detected)
        await self.audit_repo.log(
            action="onboarding_step_updated", resource_type="onboarding_session",
            resource_id=sess.id, user_id=user.id,
            details={"organization_id": organization_id, "step": step, "completed": req.completed},
        )
        await self.session.commit()
        return self._build_response(sess, detected)

    async def complete(self, user, org_context, session_id: str) -> OnboardingResponse:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        sess = await self.repo.get_for_org(session_id, organization_id)
        if sess is None:
            raise NexoraException("Onboarding session not found.", status_code=404)

        detected = await self._detect(organization_id)
        summary = await self._summary(organization_id, sess, detected)
        explicit = set(sess.completed_steps or [])
        explicit.add(S.FINISH.value)
        completed = {s for s in STEP_ORDER if detected.get(s) or s in explicit}
        progress = round(len(completed & set(STEP_ORDER)) / len(STEP_ORDER) * 100)

        sess = await self.repo.update(
            sess, status=OnboardingStatus.COMPLETED.value,
            completed_steps=sorted(explicit, key=lambda s: STEP_ORDER.index(s)),
            current_step=S.FINISH.value, progress_percent=progress, summary=summary,
        )
        # Auto-provision the org's default SRE team so incident investigation
        # works immediately (folded in from the retired infra-onboarding wizard).
        default_team = await self._ensure_default_team(organization_id, user)
        await self.audit_repo.log(
            action="onboarding_completed", resource_type="onboarding_session",
            resource_id=sess.id, user_id=user.id,
            details={"organization_id": organization_id, "progress": progress},
        )
        await self.session.commit()
        base = self._build_response(sess, detected)
        return OnboardingCompleteResponse(
            **base.model_dump(),
            default_team=default_team,
            next_actions=[
                {
                    "key": "generate_sample_incident",
                    "label": "Generate Sample Incident",
                    "endpoint": f"POST /v1/onboarding/{sess.id}/sample-incident",
                    "description": "Create a realistic sample incident (Checkout Outage) to "
                                   "explore investigation, RCA, remediation and postmortem.",
                }
            ],
        )

    async def _ensure_default_team(self, organization_id: str, user) -> dict:
        """Idempotently create the org's default SRE team + investigator/RCA agents."""
        from sqlalchemy import select

        existing = (await self.session.execute(
            select(AITeam).where(
                AITeam.organization_id == organization_id,
                AITeam.is_default.is_(True),
            ).limit(1)
        )).scalar_one_or_none()
        if existing:
            agents = (await self.session.execute(
                select(AITeamAgent).where(AITeamAgent.team_id == existing.id)
            )).scalars().all()
            return {"id": existing.id, "name": existing.name, "is_default": True,
                    "created": False, "agents": [a.name for a in agents]}

        team = AITeam(
            organization_id=organization_id,
            name="SRE Team",
            description="Default AI SRE team auto-provisioned during onboarding.",
            status=AITeamStatus.ACTIVE,
            is_default=True,
            created_by=user.id,
        )
        self.session.add(team)
        await self.session.flush()
        agent_specs = [
            ("Incident Investigator", "Incident Investigator",
             "Investigates incidents across connected read-only tools and "
             "synthesizes findings into a clear root-cause analysis."),
            ("RCA Agent", "Root Cause Analyst",
             "Correlates change events, alerts and signals to pinpoint the most "
             "likely root cause with a confidence score."),
        ]
        created_agents = []
        for name, role, description in agent_specs:
            self.session.add(AITeamAgent(
                team_id=team.id, organization_id=organization_id,
                name=name, role=role, description=description, is_active=True,
            ))
            created_agents.append(name)
        await self.session.flush()
        return {"id": team.id, "name": team.name, "is_default": True,
                "created": True, "agents": created_agents}

    async def generate_sample_incident(self, user, org_context, session_id: str) -> dict:
        """Produce a realistic sample incident via the demo scenario engine."""
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        sess = await self.repo.get_for_org(session_id, organization_id)
        if sess is None:
            raise NexoraException("Onboarding session not found.", status_code=404)
        from sqlalchemy import select

        from app.models.demo_scenario import DemoScenario, ScenarioType
        from app.services.demo_scenario import DemoScenarioService

        scenario_service = DemoScenarioService(self.session)
        await scenario_service.seed_for_org(organization_id, user)
        scenario = (await self.session.execute(
            select(DemoScenario).where(
                DemoScenario.organization_id == organization_id,
                DemoScenario.scenario_type == ScenarioType.CHECKOUT_OUTAGE.value,
            ).limit(1)
        )).scalar_one_or_none()
        if scenario is None:
            raise NotFoundError("DemoScenario", "CHECKOUT_OUTAGE")
        result = await scenario_service.run_scenario(organization_id, scenario.id, user)
        await self.session.commit()
        incident_ids = result.get("incident_ids") or []
        return {
            "scenario": "CHECKOUT_OUTAGE",
            "scenario_id": scenario.id,
            "incident_id": incident_ids[0] if incident_ids else None,
            "incident_ids": incident_ids,
            "run": result,
            "next_actions": [
                {"key": "investigate", "label": "Open the incident",
                 "endpoint": "GET /v1/incidents"},
            ],
        }

    # --------------------------------------------------------------- summary
    async def _summary(self, organization_id, sess, detected) -> str:
        connections = await self.conn_repo.list_for_org(organization_id)
        services = await self.service_repo.list_for_org(organization_id)
        deps = await self.graph.list_service_edges(organization_id)
        discoveries = await self.discovery_repo.list_for_org(organization_id, limit=1)

        done = [STEP_META[STEP_ORDER.index(s)][1] for s in STEP_ORDER
                if detected.get(s) or s in set(sess.completed_steps or [])]
        missing = [STEP_META[STEP_ORDER.index(s)][1] for s in _CORE_STEPS
                   if not (detected.get(s) or s in set(sess.completed_steps or []))]

        lines = [
            f"Onboarding summary: {len(done)}/{len(STEP_ORDER)} steps complete.",
            f"Connected integrations: {len(connections)}.",
            f"Discovery runs: {'yes' if discoveries else 'none'}.",
            f"Service catalog: {len(services)} service(s).",
            f"Dependency graph: {len(deps)} edge(s).",
        ]
        if missing:
            lines.append("Remaining to unlock full value: " + ", ".join(missing) + ".")
        else:
            lines.append("All core setup steps complete — you're ready to operate.")
        return " ".join(lines)
