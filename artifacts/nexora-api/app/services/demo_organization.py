"""Sprint 52C — Demo Organization Generator.

Creates fully functional, self-contained **demo organizations** so prospects,
trial users, and sales teams can experience the platform end-to-end without
connecting any real infrastructure.

A demo organization is a normal organization (the requesting user becomes its
OWNER) whose data is auto-generated from an industry template. The generator
seeds realistic, deterministic-but-varied data across every major subsystem so
that the existing dashboards light up immediately:

* Services, Service Dependency Graph, SLOs
* AI Teams + Agents + Workflows
* Monitoring alerts -> Incident investigations (steps, timeline, change events,
  recommendations) -> Remediation actions -> War rooms -> Postmortems
* Capacity metrics + forecasts, Cost optimization analyses
* Deployment safety / deployment history

SAFETY INVARIANTS:
* No real credentials are created or stored. Any "credential" surfaced in the
  generation summary is clearly labelled SIMULATED.
* No real cloud access and no production integrations are performed — every row
  is synthetic, customer-safe text.
* Strictly additive: reuses existing models/repositories and never mutates a
  customer's real organization.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.ai_team import AITeam, AITeamAgent, AITeamStatus, AITeamWorkflow, AITeamWorkflowStep
from app.models.capacity import CapacityForecast, CapacityMetric
from app.models.cost_optimization import CostOptimizationAnalysis
from app.models.demo_asset import DemoAsset
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
from app.models.organization import OrganizationRole
from app.models.postmortem import IncidentPostmortem
from app.models.slo import Service, ServiceSLO
from app.models.team import Team, TeamAgentMapping, TeamResponsibility, TeamStatus, TeamType
from app.models.universal_discovery import KnowledgeGraphEdge, KnowledgeGraphNode
from app.models.user import User
from app.models.war_room import WarRoom, WarRoomMessage
from app.repositories.audit import AuditLogRepository
from app.repositories.organization import (
    OrganizationMemberRepository,
    OrganizationRepository,
)
from app.services.demo_templates import DEMO_TEMPLATES
from app.services.graph import SERVICE_PREFIX, service_key

logger = get_logger(__name__)

_DEMO_MARKER = "DEMO_ORG"


def _now() -> datetime:
    return datetime.now(UTC)


# Tables purged (children first) when an org is reset/regenerated.
_PURGE_ORDER = [
    WarRoomMessage,
    WarRoom,
    IncidentPostmortem,
    IncidentRemediationApproval,
    IncidentRemediationAction,
    IncidentRecommendation,
    DeploymentChangeEvent,
    IncidentTimelineEvent,
    IncidentInvestigationStep,
    MonitoringAlert,
    IncidentInvestigation,
    ServiceSLO,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    Service,
    TeamAgentMapping,
    TeamResponsibility,
    Team,
    DemoAsset,
    AITeamWorkflowStep,
    AITeamWorkflow,
    AITeamAgent,
    AITeam,
    CapacityMetric,
    CapacityForecast,
    CostOptimizationAnalysis,
    DeploymentSafetyAnalysis,
]


class DemoOrganizationService:
    """Generate, list, regenerate, and delete demo organizations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.org_repo = OrganizationRepository(session)
        self.member_repo = OrganizationMemberRepository(session)
        self.audit_repo = AuditLogRepository(session)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def templates(self) -> list[dict]:
        out = []
        for key, tpl in DEMO_TEMPLATES.items():
            out.append(
                {
                    "key": key,
                    "name": tpl["name"],
                    "industry": tpl["industry"],
                    "summary": tpl["summary"],
                    "service_count": len(tpl["services"]),
                    "incident_count": len(tpl["incidents"]),
                    "highlights": tpl["highlights"],
                }
            )
        return out

    async def create(self, *, template: str, name: str | None, user: User) -> dict:
        tpl = DEMO_TEMPLATES.get(template)
        if not tpl:
            raise ValidationError(f"Unknown demo template '{template}'")

        org_name = (name or tpl["name"]).strip()
        slug = f"demo-{template}-{uuid.uuid4().hex[:6]}"
        description = f"{_DEMO_MARKER}::{template}:: {tpl['summary']}"

        organization = await self.org_repo.create(
            name=org_name, slug=slug, description=description
        )
        await self.member_repo.create(
            organization_id=organization.id,
            user_id=user.id,
            role=OrganizationRole.OWNER,
        )
        counts = await self._seed(organization.id, user, tpl)
        await self.audit_repo.log(
            action="demo_organization.create",
            resource_type="organization",
            resource_id=organization.id,
            user_id=user.id,
        )
        logger.info(
            "demo_organization_created",
            organization_id=organization.id,
            template=template,
        )
        return self._summary(organization, template, tpl, counts)

    async def list_for_user(self, user: User) -> list[dict]:
        orgs, _ = await self.org_repo.list_for_user(user.id, offset=0, limit=200)
        out = []
        for org in orgs:
            if not self._is_demo(org):
                continue
            template = self._template_of(org)
            tpl = DEMO_TEMPLATES.get(template, {})
            counts = await self._counts(org.id)
            out.append(
                {
                    "id": org.id,
                    "name": org.name,
                    "slug": org.slug,
                    "template": template,
                    "industry": tpl.get("industry", "—"),
                    "created_at": org.created_at,
                    "counts": counts,
                }
            )
        out.sort(key=lambda o: o["created_at"], reverse=True)
        return out

    async def regenerate(self, *, organization_id: str, user: User) -> dict:
        org = await self._owned_demo_org(organization_id, user)
        template = self._template_of(org)
        tpl = DEMO_TEMPLATES.get(template)
        if not tpl:
            raise ValidationError(
                f"Demo organization has an unknown template '{template}'"
            )
        await self._purge(org.id)
        counts = await self._seed(org.id, user, tpl)
        await self.audit_repo.log(
            action="demo_organization.regenerate",
            resource_type="organization",
            resource_id=org.id,
            user_id=user.id,
        )
        logger.info("demo_organization_regenerated", organization_id=org.id)
        return self._summary(org, template, tpl, counts)

    async def reset(self, *, organization_id: str, user: User) -> dict:
        """Clear all generated data without regenerating (empty demo org)."""
        org = await self._owned_demo_org(organization_id, user)
        await self._purge(org.id)
        await self.audit_repo.log(
            action="demo_organization.reset",
            resource_type="organization",
            resource_id=org.id,
            user_id=user.id,
        )
        template = self._template_of(org)
        tpl = DEMO_TEMPLATES.get(template, {"name": org.name})
        return self._summary(org, template, tpl, await self._counts(org.id))

    async def delete(self, *, organization_id: str, user: User) -> None:
        org = await self._owned_demo_org(organization_id, user)
        await self._purge(org.id)
        # Remove memberships then the org row itself (cascade handles the rest).
        members, _ = await self.member_repo.list_for_organization(org.id)
        for m in members:
            await self.member_repo.hard_delete(m)
        await self.org_repo.hard_delete(org)
        await self.audit_repo.log(
            action="demo_organization.delete",
            resource_type="organization",
            resource_id=organization_id,
            user_id=user.id,
        )
        logger.info("demo_organization_deleted", organization_id=organization_id)

    # ------------------------------------------------------------------ #
    # Helpers — identity / ownership
    # ------------------------------------------------------------------ #
    @staticmethod
    def _is_demo(org) -> bool:
        return bool(org.slug and org.slug.startswith("demo-")) or bool(
            org.description and org.description.startswith(_DEMO_MARKER)
        )

    @staticmethod
    def _template_of(org) -> str:
        desc = org.description or ""
        if desc.startswith(_DEMO_MARKER):
            try:
                return desc.split("::")[1]
            except IndexError:
                pass
        parts = (org.slug or "").split("-")
        return parts[1] if len(parts) >= 3 else ""

    async def _owned_demo_org(self, organization_id: str, user: User):
        org = await self.org_repo.get_by_id(organization_id)
        if not org or not self._is_demo(org):
            raise NotFoundError("Demo organization", organization_id)
        membership = await self.member_repo.get_membership(org.id, user.id)
        is_owner = membership and membership.role == OrganizationRole.OWNER
        if not (is_owner or user.is_superuser):
            raise ForbiddenError("Only the demo organization owner can manage it")
        return org

    # ------------------------------------------------------------------ #
    # Helpers — persistence
    # ------------------------------------------------------------------ #
    async def _add(self, model_cls, **kwargs):
        obj = model_cls(**kwargs)
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def _purge(self, org_id: str) -> None:
        # Join tables (e.g. team_agent_mappings) have no organization_id, so scope
        # them through their parent team instead.
        team_ids = select(Team.id).where(Team.organization_id == org_id)
        for model in _PURGE_ORDER:
            if hasattr(model, "organization_id"):
                stmt = delete(model).where(model.organization_id == org_id)
            elif hasattr(model, "team_id"):
                stmt = delete(model).where(model.team_id.in_(team_ids))
            else:
                continue
            await self.session.execute(stmt)
        await self.session.flush()

    async def _count(self, model, org_id: str) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(model).where(model.organization_id == org_id)
        )
        return int(result.scalar() or 0)

    async def _count_service_edges(self, org_id: str) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(KnowledgeGraphEdge).where(
                KnowledgeGraphEdge.organization_id == org_id,
                KnowledgeGraphEdge.source_key.like(f"{SERVICE_PREFIX}%"),
            )
        )
        return int(result.scalar() or 0)

    async def _counts(self, org_id: str) -> dict:
        return {
            "services": await self._count(Service, org_id),
            "applications": await self._count(Service, org_id),
            "slos": await self._count(ServiceSLO, org_id),
            "dependencies": await self._count_service_edges(org_id),
            "teams": await self._count(Team, org_id),
            "ai_teams": await self._count(AITeam, org_id),
            "ai_agents": await self._count(AITeamAgent, org_id),
            "workflows": await self._count(AITeamWorkflow, org_id),
            "alerts": await self._count(MonitoringAlert, org_id),
            "incidents": await self._count(IncidentInvestigation, org_id),
            "remediation_actions": await self._count(IncidentRemediationAction, org_id),
            "war_rooms": await self._count(WarRoom, org_id),
            "postmortems": await self._count(IncidentPostmortem, org_id),
            "capacity_metrics": await self._count(CapacityMetric, org_id),
            "capacity_forecasts": await self._count(CapacityForecast, org_id),
            "cost_reports": await self._count(CostOptimizationAnalysis, org_id),
            "deployments": await self._count(DeploymentSafetyAnalysis, org_id),
            "demo_assets": await self._count(DemoAsset, org_id),
        }

    # ------------------------------------------------------------------ #
    # Seeding
    # ------------------------------------------------------------------ #
    async def _seed(self, org_id: str, user: User, tpl: dict) -> dict:
        uid = user.id
        now = _now()
        cluster = tpl["clusters"][0]

        # --- 1. Services -------------------------------------------------
        services: dict[str, Service] = {}
        for spec in tpl["services"]:
            svc = await self._add(
                Service,
                organization_id=org_id,
                name=spec["name"],
                description=spec.get("description") or f"{spec['name']} ({tpl['industry']})",
                owner_team=spec.get("team", "Platform"),
                tier=f"TIER_{spec.get('tier', 2)}",
            )
            services[spec["name"]] = svc

        # --- 2. Functional teams -----------------------------------------
        await self._seed_teams(org_id, uid, tpl)

        # --- 3. SLOs -----------------------------------------------------
        for spec in tpl["services"]:
            svc = services[spec["name"]]
            await self._add(
                ServiceSLO,
                organization_id=org_id,
                service_id=svc.id,
                name=f"{spec['name']} Availability",
                slo_type="AVAILABILITY",
                target_percentage=spec.get("availability", 99.9),
                window_days=30,
            )
            await self._add(
                ServiceSLO,
                organization_id=org_id,
                service_id=svc.id,
                name=f"{spec['name']} Latency",
                slo_type="LATENCY",
                target_percentage=99.0,
                window_days=30,
                latency_percentile="P95",
                threshold_ms=float(spec.get("latency_ms", 300)),
            )

        # --- 4. Dependency graph (the single Platform Knowledge Graph) ---
        seeded_nodes: set[str] = set()
        for src, tgt, dep_type in tpl["deps"]:
            if src not in services or tgt not in services:
                continue
            for endpoint in (src, tgt):
                svc = services[endpoint]
                if svc.id not in seeded_nodes:
                    await self._add(
                        KnowledgeGraphNode,
                        organization_id=org_id,
                        node_key=service_key(svc.id),
                        node_type="SERVICE",
                        name=svc.name,
                        last_seen_at=now,
                    )
                    seeded_nodes.add(svc.id)
            await self._add(
                KnowledgeGraphEdge,
                organization_id=org_id,
                source_key=service_key(services[src].id),
                target_key=service_key(services[tgt].id),
                relationship_type=dep_type,
                edge_metadata={"dependency_type": dep_type, "origin": "catalog"},
                last_seen_at=now,
            )

        # --- 5. AI Team + Agents + Workflow -----------------------------
        team = await self._add(
            AITeam,
            organization_id=org_id,
            name="SRE Response Team",
            description=f"Reliability AI team for the {tpl['name']} demo.",
            status=AITeamStatus.ACTIVE,
            created_by=uid,
        )
        agent_specs = [
            ("SRE Lead", "Site Reliability Lead", "Coordinate incident response and own RCA synthesis."),
            ("Kubernetes Specialist", "Platform/Kubernetes", "Inspect workloads, rollouts, and pod health."),
            ("Database Reliability", "Database SRE", "Investigate query latency, locks, and replication."),
            ("Security Analyst", "Security", "Assess blast radius and security implications."),
            ("Release Manager", "Release/Deploy", "Correlate recent deployments and changes."),
        ]
        agents: dict[str, AITeamAgent] = {}
        for nm, role, instr in agent_specs:
            agents[nm] = await self._add(
                AITeamAgent,
                team_id=team.id,
                organization_id=org_id,
                name=nm,
                role=role,
                description=instr,
                instructions=instr,
                model="gpt-5",
                is_active=True,
            )
        workflow = await self._add(
            AITeamWorkflow,
            organization_id=org_id,
            team_id=team.id,
            name="Incident Response Runbook",
            description="Triage -> investigate -> correlate change -> recommend remediation.",
            default_prompt="Investigate the active incident and propose a remediation plan.",
            is_active=True,
        )
        for i, nm in enumerate(["SRE Lead", "Kubernetes Specialist", "Database Reliability", "Release Manager"], start=1):
            await self._add(
                AITeamWorkflowStep,
                workflow_id=workflow.id,
                agent_id=agents[nm].id,
                step_order=i,
                custom_instructions=f"Step {i}: {nm} contributes findings.",
                requires_approval=(nm == "Release Manager"),
                approval_name="Remediation approval" if nm == "Release Manager" else None,
                approver_role="OWNER" if nm == "Release Manager" else None,
            )

        # --- 6. Incidents + alerts + war rooms + postmortems ------------
        for idx, scen in enumerate(tpl["incidents"]):
            await self._seed_incident(org_id, uid, team, agents, scen, idx, now)

        # --- 7. Standalone monitoring alerts (no incident) --------------
        for j, spec in enumerate(tpl["services"][:4]):
            sev = ["INFO", "WARNING", "WARNING", "HIGH"][j % 4]
            seen = now - timedelta(hours=6 * (j + 1))
            await self._add(
                MonitoringAlert,
                organization_id=org_id,
                provider="PROMETHEUS",
                alert_id=f"demo-alert-{j}-{uuid.uuid4().hex[:6]}",
                alert_name=f"{spec['name']} elevated latency",
                severity=sev,
                status="RESOLVED" if j % 2 == 0 else "FIRING",
                service=spec["name"],
                environment="production",
                description=f"p95 latency on {spec['name']} crossed the warning threshold.",
                first_seen_at=seen,
                last_seen_at=seen + timedelta(minutes=20),
                occurrence_count=1 + j,
            )

        # --- 8. Capacity metrics + forecasts ----------------------------
        await self._seed_capacity(org_id, uid, tpl, cluster, now)

        # --- 9. Cost optimization analyses ------------------------------
        await self._seed_cost(org_id, uid, tpl, cluster)

        # --- 10. Deployment safety / history ----------------------------
        await self._seed_deployments(org_id, uid, tpl, now)

        # --- 11. Screenshot metadata assets ------------------------------
        await self._seed_demo_assets(org_id, uid, tpl)

        await self.session.flush()
        return await self._counts(org_id)

    async def _seed_teams(self, org_id: str, uid: str, tpl: dict) -> None:
        team_to_service_count: dict[str, int] = {}
        for spec in tpl["services"]:
            name = spec.get("team", "Platform")
            team_to_service_count[name] = team_to_service_count.get(name, 0) + 1

        def team_type_for(name: str) -> TeamType:
            key = name.lower()
            if "front" in key or "ui" in key:
                return TeamType.FRONTEND
            if "back" in key or "api" in key:
                return TeamType.BACKEND
            if "qa" in key or "test" in key:
                return TeamType.QA
            if "devops" in key or "platform" in key or "sre" in key:
                return TeamType.DEVOPS
            if "security" in key:
                return TeamType.SECURITY
            if "product" in key:
                return TeamType.PRODUCT
            return TeamType.CUSTOM

        mapping_by_type: dict[TeamType, list[tuple[str, int, bool]]] = {
            TeamType.FRONTEND: [("frontend_v1", 1, True), ("uiux_designer", 2, True)],
            TeamType.BACKEND: [("backend_v1", 1, True), ("backend_code_review", 2, True)],
            TeamType.DEVOPS: [("cicd_agent", 1, True), ("kubernetes_agent", 2, True)],
            TeamType.SECURITY: [("security_test", 1, True), ("qa_approval", 2, False)],
            TeamType.PRODUCT: [("business_analyst", 1, True), ("fullstack_assembly", 2, False)],
            TeamType.QA: [("integration_test", 1, True), ("unit_test_generator", 2, True)],
            TeamType.CUSTOM: [("business_analyst", 1, True)],
        }
        for team_name, svc_count in team_to_service_count.items():
            t_type = team_type_for(team_name)
            row = await self._add(
                Team,
                organization_id=org_id,
                name=team_name,
                description=f"{team_name} team for the {tpl['industry']} demo organization.",
                team_type=t_type,
                status=TeamStatus.ACTIVE,
                created_by=uid,
            )
            await self._add(
                TeamResponsibility,
                team_id=row.id,
                title="Service ownership",
                description=f"Owns {svc_count} demo services in this organization.",
                priority="HIGH",
            )
            await self._add(
                TeamResponsibility,
                team_id=row.id,
                title="Incident response",
                description="Participates in war room decisions and remediation approvals.",
                priority="CRITICAL",
            )
            for agent_name, order, is_required in mapping_by_type.get(t_type, mapping_by_type[TeamType.CUSTOM]):
                await self._add(
                    TeamAgentMapping,
                    team_id=row.id,
                    internal_agent=agent_name,
                    execution_order=order,
                    is_required=is_required,
                )

    async def _seed_demo_assets(self, org_id: str, uid: str, tpl: dict) -> None:
        slug = tpl["name"].lower().replace(" ", "-").replace("(", "").replace(")", "")
        screenshots = [
            ("Incidents overview", "INCIDENTS", "incidents", "Active incident investigations and RCA confidence."),
            ("War room consensus", "WAR_ROOM", "war-room", "Live multi-agent debate and remediation consensus."),
            ("Service health SLOs", "SLO", "service-health", "SLO compliance and error-budget burn trends."),
            ("Dependency graph", "DISCOVERY", "dependency-graph", "Service dependency paths and blast radius."),
            ("Capacity forecast", "CAPACITY", "capacity", "Resource saturation forecasts and scale actions."),
            ("Cost optimization", "COST", "cost-optimization", "Waste analysis and projected annual savings."),
            ("Deployment history", "CHANGE_INTELLIGENCE", "deployment-safety", "Recent release risk/readiness timeline."),
        ]
        for idx, (title, category, module, desc) in enumerate(screenshots, start=1):
            await self._add(
                DemoAsset,
                organization_id=org_id,
                title=title,
                description=f"{desc} Generated for {tpl['name']}.",
                category=category,
                asset_type="SCREENSHOT",
                module=module,
                url=f"https://demo.local/assets/{slug}/{module}.png",
                thumbnail_url=f"https://demo.local/assets/{slug}/{module}-thumb.png",
                mime_type="image/png",
                file_size=180_000 + idx * 12_000,
                width=1920,
                height=1080,
                tags=["demo", tpl["industry"].lower().replace("-", "_"), module],
                order_index=idx,
                created_by=uid,
            )

    async def _seed_incident(self, org_id, uid, team, agents, scen, idx, now):
        started = now - timedelta(days=scen.get("days_ago", idx + 1), hours=scen.get("hours", 3))
        resolved = scen.get("status", "COMPLETED") == "COMPLETED"
        sev = scen.get("severity", "HIGH")

        inv = await self._add(
            IncidentInvestigation,
            organization_id=org_id,
            team_id=team.id,
            agent_id=agents["SRE Lead"].id,
            title=scen["title"],
            prompt=f"Investigate: {scen['title']} affecting {scen['service']}.",
            status="COMPLETED" if resolved else "RUNNING",
            summary=scen.get("summary") if resolved else None,
            root_cause=scen.get("root_cause") if resolved else None,
            recommendations=scen.get("resolution") if resolved else None,
            confidence_score=scen.get("confidence", 88) if resolved else None,
            suspected_trigger=scen.get("trigger"),
            suspected_provider=scen.get("change_provider", "GITHUB"),
            source="MONITORING",
            severity=sev,
            created_by=uid,
            created_at=started,
        )

        # Triggering alert linked to the incident.
        await self._add(
            MonitoringAlert,
            organization_id=org_id,
            provider=scen.get("provider", "PROMETHEUS"),
            alert_id=f"demo-alert-inc-{idx}-{uuid.uuid4().hex[:6]}",
            alert_name=scen.get("alert_name", scen["title"]),
            severity=sev,
            status="RESOLVED" if resolved else "FIRING",
            service=scen["service"],
            environment="production",
            description=scen.get("alert_desc", f"{scen['service']}: {scen['title']}"),
            first_seen_at=started,
            last_seen_at=started + timedelta(minutes=scen.get("duration_min", 45)),
            occurrence_count=scen.get("occurrences", 3),
            incident_id=inv.id,
        )

        # Investigation steps (read-only tool actions).
        steps = scen.get(
            "steps",
            [
                ("PROMETHEUS", "Query error-rate & latency metrics"),
                ("KUBERNETES", "Inspect pod restarts and rollout status"),
                ("GITHUB", "List recent deployments and PRs"),
                ("DATADOG", "Review APM traces for slow spans"),
            ],
        )
        for so, (prov, action) in enumerate(steps, start=1):
            await self._add(
                IncidentInvestigationStep,
                investigation_id=inv.id,
                organization_id=org_id,
                step_order=so,
                tool_provider=prov,
                action=action,
                status="COMPLETED",
                result_summary=f"{action}: evidence collected for {scen['service']}.",
                execution_time_ms=400 + so * 120,
            )

        # Timeline events.
        tl = [
            ("DEPLOYMENT", "Deployment completed", started - timedelta(minutes=25), "INFO"),
            ("ALERT", scen.get("alert_name", "Alert fired"), started, "CRITICAL" if sev == "CRITICAL" else "WARNING"),
            ("METRIC", "Error rate spiked", started + timedelta(minutes=2), "WARNING"),
        ]
        if resolved:
            tl.append(("INCIDENT", "Incident mitigated", started + timedelta(minutes=scen.get("duration_min", 45)), "INFO"))
        for prov_evt in tl:
            etype, title, ts, esev = prov_evt
            await self._add(
                IncidentTimelineEvent,
                investigation_id=inv.id,
                organization_id=org_id,
                provider="PROMETHEUS" if etype in ("ALERT", "METRIC") else "GITHUB",
                event_type=etype,
                event_timestamp=ts,
                title=title,
                description=f"{title} for {scen['service']}.",
                severity=esev,
                event_metadata={"service": scen["service"]},
            )

        # Change event (suspected trigger).
        await self._add(
            DeploymentChangeEvent,
            investigation_id=inv.id,
            organization_id=org_id,
            provider=scen.get("change_provider", "GITHUB"),
            change_type="DEPLOYMENT",
            change_timestamp=started - timedelta(minutes=25),
            actor=scen.get("actor", "ci-bot"),
            title=scen.get("trigger", "Recent deployment"),
            description=scen.get("trigger", "A recent deployment preceded the incident."),
            version=scen.get("version", "v1.4.2"),
            event_metadata={"service": scen["service"]},
        )

        # Recommendations.
        recs = scen.get(
            "recs",
            [
                ("Deployment", f"Roll back {scen['service']} to the last healthy version", "MEDIUM", 90, 10),
                ("Monitoring", "Tighten alert thresholds and add a burn-rate alert", "LOW", 70, 15),
            ],
        )
        rec_rows = []
        for ro, (rtype, rtitle, risk, conf, mins) in enumerate(recs, start=1):
            rec = await self._add(
                IncidentRecommendation,
                investigation_id=inv.id,
                organization_id=org_id,
                recommendation_type=rtype,
                title=rtitle,
                description=f"{rtitle}. Estimated recovery ~{mins} min.",
                risk_level=risk,
                confidence_score=conf,
                estimated_recovery_minutes=mins,
                recommendation_order=ro,
                event_metadata={"service": scen["service"]},
            )
            rec_rows.append(rec)

        # Remediation action (approval-gated, never auto-executed).
        if scen.get("remediation", True) and rec_rows:
            action = await self._add(
                IncidentRemediationAction,
                organization_id=org_id,
                investigation_id=inv.id,
                recommendation_id=rec_rows[0].id,
                action_type="ROLLBACK",
                provider=scen.get("change_provider", "KUBERNETES"),
                title=f"Roll back {scen['service']}",
                description=f"Roll back {scen['service']} to the last healthy revision.",
                risk_level="MEDIUM",
                environment="production",
                application=scen["service"],
                target_config={"strategy": "rollback", "service": scen["service"]},
                status="PENDING_APPROVAL",
                action_metadata={"demo": True},
            )
            await self._add(
                IncidentRemediationApproval,
                organization_id=org_id,
                action_id=action.id,
                status="PENDING",
                comments="Awaiting human approval (demo).",
            )

        # War room for major incidents.
        if scen.get("war_room"):
            await self._seed_war_room(org_id, uid, inv, scen, started)

        # Postmortem for resolved incidents.
        if resolved and scen.get("postmortem", True):
            await self._seed_postmortem(org_id, uid, inv, scen, started)

    async def _seed_war_room(self, org_id, uid, inv, scen, started):
        agents_in_room = ["CTO", "SRE", "KUBERNETES", "GITHUB", "DATABASE", "SECURITY"]
        room = await self._add(
            WarRoom,
            organization_id=org_id,
            incident_id=inv.id,
            title=f"War Room — {scen['title']}",
            status="AWAITING_APPROVAL",
            summary=scen.get("summary", f"Coordinated response to {scen['title']}."),
            consensus_rca=scen.get("root_cause", "Recent deployment regression."),
            remediation_plan=[
                {"step": 1, "action": f"Roll back {scen['service']}", "risk": "MEDIUM"},
                {"step": 2, "action": "Verify SLO recovery and error budget", "risk": "LOW"},
            ],
            confidence_score=scen.get("confidence", 88),
            participating_agents=agents_in_room,
            requires_approval=True,
            message_count=0,
            created_by=uid,
            created_at=started + timedelta(minutes=3),
        )
        msgs = [
            ("SYSTEM", "INFO", f"War room opened for '{scen['title']}'."),
            ("SRE", "FINDING", f"Error rate on {scen['service']} jumped right after a deploy."),
            ("GITHUB", "FINDING", f"Suspect change: {scen.get('trigger', 'recent deployment')}."),
            ("KUBERNETES", "FINDING", "Rollout shows elevated restart count on new pods."),
            ("DATABASE", "CHALLENGE", "DB metrics look nominal — not a datastore issue."),
            ("SECURITY", "INFO", "No security indicators; blast radius limited to one service."),
            ("CTO", "HYPOTHESIS", "Most likely a regression in the latest release."),
            ("SRE", "REMEDIATION", f"Recommend rolling back {scen['service']} immediately."),
            ("CTO", "CONSENSUS", "Consensus: roll back and re-validate SLOs. Awaiting approval."),
        ]
        for seq, (agent, mtype, content) in enumerate(msgs, start=1):
            await self._add(
                WarRoomMessage,
                war_room_id=room.id,
                organization_id=org_id,
                agent=agent,
                message_type=mtype,
                content=content,
                confidence=scen.get("confidence", 88) if mtype == "CONSENSUS" else None,
                citations=[{"type": "incident", "id": inv.id}] if mtype == "CONSENSUS" else None,
                sequence=seq,
            )
        room.message_count = len(msgs)
        await self.session.flush()

    async def _seed_postmortem(self, org_id, uid, inv, scen, started):
        await self._add(
            IncidentPostmortem,
            organization_id=org_id,
            investigation_id=inv.id,
            title=f"Postmortem — {scen['title']}",
            status="GENERATED",
            severity=scen.get("severity", "HIGH"),
            source="MONITORING",
            confidence_score=scen.get("confidence", 88),
            version=1,
            generated_by="AUTO",
            executive_summary=scen.get(
                "summary", f"{scen['service']} experienced a regression following a deployment."
            ),
            impact_analysis=f"Customers experienced degraded {scen['service']} performance for "
            f"~{scen.get('duration_min', 45)} minutes.",
            timeline_summary="Deployment -> alert fired -> error spike -> rollback -> recovery.",
            root_cause=scen.get("root_cause", "Regression introduced by a recent deployment."),
            triggering_change=scen.get("trigger", "Recent deployment"),
            resolution=scen.get("resolution", "Rolled back to the last healthy version; SLOs recovered."),
            lessons_learned="Add burn-rate alerts and require canary rollout for this service.",
            action_items=[
                {
                    "title": f"Add canary rollout for {scen['service']}",
                    "detail": "Gate releases behind a 10% canary with auto-rollback.",
                    "owner": "Release Manager",
                    "status": "OPEN",
                    "source": "postmortem",
                    "risk_level": "LOW",
                },
                {
                    "title": "Add burn-rate SLO alert",
                    "detail": "Page when 1h burn-rate exceeds 2x budget.",
                    "owner": "SRE Lead",
                    "status": "OPEN",
                    "source": "postmortem",
                    "risk_level": "LOW",
                },
            ],
            content_markdown=f"# Postmortem — {scen['title']}\n\n"
            f"**Service:** {scen['service']}\n\n"
            f"**Root cause:** {scen.get('root_cause', 'Deployment regression.')}\n",
            created_by=uid,
            created_at=started + timedelta(hours=2),
        )

    async def _seed_capacity(self, org_id, uid, tpl, cluster, now):
        resources = [("CPU", "cores", 32.0), ("MEMORY", "GB", 128.0)]
        for spec in tpl["services"][:4]:
            for rtype, unit, cap in resources:
                base = cap * tpl.get("util", 0.55)
                growth = cap * 0.012
                for d in range(7):
                    recorded = now - timedelta(days=6 - d)
                    usage = base + growth * d
                    await self._add(
                        CapacityMetric,
                        organization_id=org_id,
                        cluster=cluster,
                        service=spec["name"],
                        environment="production",
                        resource_type=rtype,
                        usage=round(usage, 2),
                        capacity=cap,
                        unit=unit,
                        recorded_at=recorded,
                    )
                cur = base + growth * 6
                util = round(cur / cap * 100, 1)
                f30 = base + growth * 36
                status = "CRITICAL" if util > 85 else "WARNING" if util > 70 else "HEALTHY"
                await self._add(
                    CapacityForecast,
                    organization_id=org_id,
                    cluster=cluster,
                    service=spec["name"],
                    environment="production",
                    resource_type=rtype,
                    unit=unit,
                    current_usage=round(cur, 2),
                    capacity=cap,
                    current_utilization=util,
                    growth_rate_per_day=round(growth, 3),
                    trend="GROWING",
                    forecast_7d=round(base + growth * 13, 2),
                    forecast_30d=round(f30, 2),
                    forecast_90d=round(base + growth * 96, 2),
                    saturation_threshold=90.0,
                    saturation_date=now + timedelta(days=40),
                    status=status,
                    recommendation_action="ADD_NODES" if status != "HEALTHY" else "NONE",
                    recommendation=(
                        f"Scale {spec['name']} before projected saturation."
                        if status != "HEALTHY"
                        else "Capacity healthy for the forecast window."
                    ),
                    current_cost=round(cur * 12, 2),
                    projected_cost=round(f30 * 12, 2),
                    delta_cost=round((f30 - cur) * 12, 2),
                    confidence=0.9,
                    data_points=7,
                    details={"service": spec["name"]},
                    created_by=uid,
                )

    async def _seed_cost(self, org_id, uid, tpl, cluster):
        # Org-level summary analysis.
        current = float(tpl.get("monthly_spend", 48000))
        waste = round(current * tpl.get("waste_pct", 0.22), 2)
        savings = round(waste * 0.85, 2)
        optimized = round(current - savings, 2)
        score = max(40, 100 - int(tpl.get("waste_pct", 0.22) * 200))
        level = (
            "EXCELLENT" if score >= 85 else "GOOD" if score >= 70 else "NEEDS_IMPROVEMENT" if score >= 55 else "CRITICAL_WASTE"
        )
        await self._add(
            CostOptimizationAnalysis,
            organization_id=org_id,
            cluster=cluster,
            service=None,
            environment="production",
            current_cost=current,
            estimated_waste=waste,
            potential_savings=savings,
            optimized_cost=optimized,
            annual_savings=round(savings * 12, 2),
            savings_percentage=round(savings / current * 100, 1),
            optimization_score=score,
            optimization_level=level,
            forecast_30d=current,
            forecast_90d=round(current * 3, 2),
            forecast_365d=round(current * 12, 2),
            idle_count=3,
            overprovisioned_count=4,
            nonprod_count=2,
            confidence=0.88,
            details={"scope": "organization"},
            created_by=uid,
        )
        # Per-service analyses.
        for i, spec in enumerate(tpl["services"][:3]):
            cur = round(current / 6 * (1 + i * 0.1), 2)
            w = round(cur * 0.18, 2)
            sv = round(w * 0.8, 2)
            await self._add(
                CostOptimizationAnalysis,
                organization_id=org_id,
                cluster=cluster,
                service=spec["name"],
                environment="production",
                current_cost=cur,
                estimated_waste=w,
                potential_savings=sv,
                optimized_cost=round(cur - sv, 2),
                annual_savings=round(sv * 12, 2),
                savings_percentage=round(sv / cur * 100, 1),
                optimization_score=max(50, 90 - i * 10),
                optimization_level="GOOD",
                forecast_30d=cur,
                forecast_90d=round(cur * 3, 2),
                forecast_365d=round(cur * 12, 2),
                idle_count=1,
                overprovisioned_count=1 + i,
                nonprod_count=1,
                confidence=0.85,
                details={"service": spec["name"]},
                created_by=uid,
            )

    async def _seed_deployments(self, org_id, uid, tpl, now):
        strategies = ["FULL_ROLLOUT", "CANARY_10", "BLUE_GREEN", "CANARY_25"]
        readiness_cycle = ["READY", "READY", "AT_RISK", "READY", "NOT_READY", "READY"]
        n = 0
        for si, spec in enumerate(tpl["services"]):
            for rev in range(2):
                n += 1
                readiness = readiness_cycle[n % len(readiness_cycle)]
                blast = "HIGH" if spec.get("tier", 2) == 1 else "MEDIUM" if spec.get("tier", 2) == 2 else "LOW"
                safety = 92 if readiness == "READY" else 64 if readiness == "AT_RISK" else 38
                await self._add(
                    DeploymentSafetyAnalysis,
                    organization_id=org_id,
                    service=spec["name"],
                    environment="production",
                    version=f"v1.{4 + si}.{rev}",
                    provider="KUBERNETES",
                    safety_score=safety,
                    confidence=0.9,
                    readiness=readiness,
                    blast_radius=blast,
                    recommended_strategy=strategies[n % len(strategies)],
                    recommended_window="Tue–Thu, 10:00–15:00 (low traffic)",
                    risk_score=100 - safety,
                    risk_level="LOW" if safety >= 80 else "MEDIUM" if safety >= 50 else "HIGH",
                    warnings=[] if readiness == "READY" else ["Recent incident on this service", "Elevated error budget burn"],
                    details={"service": spec["name"], "history": True},
                    created_by=uid,
                    created_at=now - timedelta(days=14 - n),
                )

    # ------------------------------------------------------------------ #
    # Summary / synthetic assets
    # ------------------------------------------------------------------ #
    def _summary(self, organization, template: str, tpl: dict, counts: dict) -> dict:
        slug = organization.slug
        return {
            "id": organization.id,
            "name": organization.name,
            "slug": slug,
            "template": template,
            "industry": tpl.get("industry", "—"),
            "counts": counts,
            "credentials": {
                "owner_role": "OWNER",
                "note": "Demo organization — no real infrastructure or production "
                "credentials are connected. All data is synthetic.",
                "simulated_integrations": [
                    {"provider": "AWS", "status": "SIMULATED", "access_key": "AKIA-DEMO-XXXXXXXX"},
                    {"provider": "KUBERNETES", "status": "SIMULATED", "context": "demo-cluster"},
                    {"provider": "DATADOG", "status": "SIMULATED", "api_key": "dd-demo-************"},
                    {"provider": "GITHUB", "status": "SIMULATED", "token": "ghp_demo_************"},
                ],
            },
            "dashboards": [
                {"name": "Service Health", "path": "#/service-health"},
                {"name": "Dependency Graph", "path": "#/dependency-graph"},
                {"name": "Incidents", "path": "#/incidents"},
                {"name": "War Room", "path": "#/war-room"},
                {"name": "Postmortems", "path": "#/postmortems"},
                {"name": "Capacity Planning", "path": "#/capacity"},
                {"name": "Cost Optimization", "path": "#/cost-optimization"},
                {"name": "Deployment Safety", "path": "#/deployment-safety"},
            ],
            "screenshots": [
                {"module": "incidents", "filename": f"{slug}-incidents.png", "caption": "Incident investigation with RCA"},
                {"module": "war-room", "filename": f"{slug}-war-room.png", "caption": "Multi-agent war room consensus"},
                {"module": "service-health", "filename": f"{slug}-slo.png", "caption": "Service health & SLO compliance"},
                {"module": "dependency-graph", "filename": f"{slug}-graph.png", "caption": "Service dependency graph & blast radius"},
                {"module": "capacity", "filename": f"{slug}-capacity.png", "caption": "Capacity forecast & saturation"},
                {"module": "cost", "filename": f"{slug}-cost.png", "caption": "Cost optimization report"},
            ],
            "reports": [
                {"type": "SLO", "name": "Service Health & SLO report", "items": counts.get("slos", 0)},
                {"type": "CAPACITY", "name": "Capacity forecast report", "items": counts.get("capacity_forecasts", 0)},
                {"type": "COST", "name": "Cost optimization report", "items": counts.get("cost_reports", 0)},
                {"type": "POSTMORTEM", "name": "Incident postmortems", "items": counts.get("postmortems", 0)},
                {"type": "DEPLOYMENT", "name": "Deployment safety history", "items": counts.get("deployments", 0)},
            ],
        }
