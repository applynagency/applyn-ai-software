"""Service Dependency & Blast Radius — read views over the single graph.

Read-only intelligence over the directed service topology (``source
--depends-on--> target``) that lives in the single Platform Knowledge Graph.
All traversal is delegated to :class:`app.services.graph.GraphService` (the one
traversal engine); all writes are delegated to
:class:`app.services.universal_discovery.UniversalDiscoveryService` (the one graph
writer). This service only adds RBAC, validation, audit and the API-facing
projections (dependency views, blast radius, dashboard).

Direction & terminology
------------------------
* Edge: source depends on target.
* downstream_services (dependencies): services this one depends on  (follow source→target).
* upstream_services  (dependents):    services that depend on this one (follow target←source).
* Blast radius of an incident on service X = X's transitive dependents — they
  rely on X, so they are impacted when X degrades.
"""

from __future__ import annotations

from collections import defaultdict

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NexoraException
from app.models.slo import ServiceTier
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.incident import IncidentInvestigationRepository, MonitoringAlertRepository
from app.repositories.oncall import IncidentAssignmentRepository
from app.repositories.slo import ServiceRepository
from app.schemas.service_dependency import (
    BlastRadius,
    BlastRadiusDashboard,
    BlastRadiusService,
    DependencyEdge,
    DependencyGraph,
    DependencyType,
    GraphNode,
    ServiceDependencyView,
    ServiceRef,
)
from app.services.graph import GraphService, is_service_key
from app.services.universal_discovery import UniversalDiscoveryService
from app.tenancy.permissions import can_read_ai_teams, can_write_ai_teams

logger = structlog.get_logger(__name__)

_TIER_WEIGHT = {ServiceTier.TIER_1.value: 3, ServiceTier.TIER_2.value: 2, ServiceTier.TIER_3.value: 1}


class DependencyGraphService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.graph_svc = GraphService(session)
        self.writer = UniversalDiscoveryService(session)
        self.service_repo = ServiceRepository(session)
        self.incident_repo = IncidentInvestigationRepository(session)
        self.assignment_repo = IncidentAssignmentRepository(session)
        self.alert_repo = MonitoringAlertRepository(session)
        self.audit_repo = AuditLogRepository(session)

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

    # --------------------------------------------------------------- CRUD
    async def add_dependency(self, user, org_context, data) -> DependencyEdge:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)

        if data.source_service_id == data.target_service_id:
            raise NexoraException("A service cannot depend on itself.", status_code=400)

        source = await self.service_repo.get_for_org(data.source_service_id, organization_id)
        target = await self.service_repo.get_for_org(data.target_service_id, organization_id)
        if source is None or target is None:
            raise NexoraException("Source or target service not found.", status_code=404)

        dtype = (data.dependency_type or "SYNC").upper()
        if dtype not in {t.value for t in DependencyType}:
            raise NexoraException(
                f"Invalid dependency_type. One of {[t.value for t in DependencyType]}.",
                status_code=400,
            )

        existing = await self.graph_svc.find_service_edge(
            organization_id, data.source_service_id, data.target_service_id
        )
        if existing is not None:
            raise NexoraException("This dependency already exists.", status_code=409)

        edge = await self.writer.add_service_dependency(
            organization_id,
            source_service_id=data.source_service_id,
            target_service_id=data.target_service_id,
            dependency_type=dtype,
            source_name=source.name,
            target_name=target.name,
        )
        await self.audit_repo.log(
            action="service_dependency_created",
            resource_type="service_dependency",
            resource_id=edge.id,
            user_id=user.id,
            details={
                "organization_id": organization_id,
                "source": source.name,
                "target": target.name,
                "dependency_type": dtype,
            },
        )
        await self.session.commit()
        return DependencyEdge(
            id=edge.id,
            organization_id=organization_id,
            source_service_id=data.source_service_id,
            source_name=source.name,
            target_service_id=data.target_service_id,
            target_name=target.name,
            dependency_type=dtype,
            created_at=edge.created_at,
        )

    async def list_dependencies(self, user, org_context) -> list[DependencyEdge]:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        edges = await self.graph_svc.list_service_edges(organization_id)
        names = {s.id: s.name for s in await self.service_repo.list_for_org(organization_id)}
        return [self._edge(e, names) for e in edges]

    async def delete_dependency(self, user, org_context, dependency_id) -> None:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        edge = await self.graph_svc.get_edge_row(organization_id, dependency_id)
        if edge is None or not is_service_key(edge.source_key):
            raise NexoraException("Dependency not found.", status_code=404)
        await self.writer.remove_service_dependency(edge)
        await self.audit_repo.log(
            action="service_dependency_deleted",
            resource_type="service_dependency",
            resource_id=dependency_id,
            user_id=user.id,
            details={"organization_id": organization_id},
        )
        await self.session.commit()

    # ------------------------------------------------------------- graph views
    async def graph(self, user, org_context) -> DependencyGraph:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        services = await self.service_repo.list_for_org(organization_id)
        edges = await self.graph_svc.list_service_edges(organization_id)
        g = await self.graph_svc.service_adjacency(organization_id)
        names = {s.id: s.name for s in services}
        nodes = [
            GraphNode(
                id=s.id, name=s.name, tier=s.tier, owner_team=s.owner_team,
                dependency_count=len(g.out_edges.get(s.id, set())),
                dependent_count=len(g.in_edges.get(s.id, set())),
            )
            for s in services
        ]
        await self.audit_repo.log(
            action="dependency_graph_viewed",
            resource_type="service_dependency",
            resource_id=organization_id,
            user_id=user.id,
            details={"organization_id": organization_id, "nodes": len(nodes), "edges": len(edges)},
        )
        await self.session.commit()
        return DependencyGraph(nodes=nodes, edges=[self._edge(e, names) for e in edges])

    async def service_dependencies(self, user, org_context, service_id) -> ServiceDependencyView:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        service = await self.service_repo.get_for_org(service_id, organization_id)
        if service is None:
            raise NexoraException("Service not found.", status_code=404)

        services = await self.service_repo.list_for_org(organization_id)
        by_id = {s.id: s for s in services}
        g = await self.graph_svc.service_adjacency(organization_id)

        dep_direct, dep_all = g.dependencies(service_id)
        dpt_direct, dpt_all = g.dependents(service_id)

        def refs(ids):
            return [self._ref(by_id[i]) for i in ids if i in by_id]

        dep_indirect = dep_all - dep_direct
        dpt_indirect = dpt_all - dpt_direct

        await self.audit_repo.log(
            action="service_dependencies_viewed",
            resource_type="service",
            resource_id=service_id,
            user_id=user.id,
            details={
                "organization_id": organization_id,
                "dependencies": len(dep_all),
                "dependents": len(dpt_all),
            },
        )
        await self.session.commit()

        return ServiceDependencyView(
            service=self._ref(service),
            direct_dependencies=refs(dep_direct),
            indirect_dependencies=refs(dep_indirect),
            downstream_services=refs(dep_all),
            direct_dependents=refs(dpt_direct),
            indirect_dependents=refs(dpt_indirect),
            upstream_services=refs(dpt_all),
            has_cycle=g.has_cycle(),
        )

    # ----------------------------------------------------------- blast radius
    async def blast_radius(self, user, org_context, incident_id) -> BlastRadius:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        incident = await self.incident_repo.get_for_org(incident_id, organization_id)
        if incident is None:
            raise NexoraException("Incident not found.", status_code=404)

        origin_name, resolved_from = await self._resolve_origin_service(organization_id, incident)

        services = await self.service_repo.list_for_org(organization_id)
        by_id = {s.id: s for s in services}
        by_name = {s.name: s for s in services}
        g = await self.graph_svc.service_adjacency(organization_id)

        origin = by_name.get(origin_name) if origin_name else None

        result = BlastRadius(
            incident_id=incident_id,
            origin_service_name=origin_name,
            resolved_from=resolved_from,
            severity=incident.severity,
        )

        if origin is None:
            result.customer_impact_level = "LOW"
            result.customer_impact = "Unknown — the affected service is not in the service catalog."
            result.summary = (
                "Could not map this incident to a catalogued service"
                + (f" (signal: '{origin_name}')." if origin_name else ".")
            )
            return result

        result.origin_service_id = origin.id
        direct, transitive = g.dependents(origin.id)  # who depends on origin → impacted

        def refs(ids):
            return [self._ref(by_id[i]) for i in ids if i in by_id]

        indirect = transitive - direct
        affected = transitive
        result.direct_impact = refs(direct)
        result.indirect_impact = refs(indirect)
        result.affected_services = refs(affected)
        result.affected_count = len(affected)

        # Tier breakdown over origin + affected.
        tier_breakdown: dict[str, int] = defaultdict(int)
        tier_breakdown[origin.tier] += 1
        for sid in affected:
            svc = by_id.get(sid)
            if svc:
                tier_breakdown[svc.tier] += 1
        result.tier_breakdown = dict(tier_breakdown)

        level = self._impact_level(origin, [by_id[i] for i in affected if i in by_id], incident.severity)
        result.customer_impact_level = level
        result.customer_impact = self._impact_text(level, len(affected), tier_breakdown)
        result.summary = (
            f"Incident on '{origin.name}' ({origin.tier}) impacts {len(affected)} dependent "
            f"service(s) — {len(direct)} directly. Customer impact: {level}."
        )

        await self.audit_repo.log(
            action="blast_radius_viewed",
            resource_type="incident_investigation",
            resource_id=incident_id,
            user_id=user.id,
            details={
                "organization_id": organization_id,
                "origin_service": origin.name,
                "affected_count": len(affected),
                "impact_level": level,
            },
        )
        await self.session.commit()
        return result

    async def dashboard(self, user, org_context) -> BlastRadiusDashboard:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        services = await self.service_repo.list_for_org(organization_id)
        edges = await self.graph_svc.list_service_edges(organization_id)
        g = await self.graph_svc.service_adjacency(organization_id)

        rows: list[BlastRadiusService] = []
        for s in services:
            _, transitive_dependents = g.dependents(s.id)
            deps_direct = g.out_edges.get(s.id, set())
            affected = [x for x in services if x.id in transitive_dependents]
            level = self._impact_level(s, affected, None)
            rows.append(
                BlastRadiusService(
                    service=self._ref(s),
                    dependencies_count=len(deps_direct),
                    dependents_count=len(g.in_edges.get(s.id, set())),
                    blast_radius_size=len(transitive_dependents),
                    impact_level=level,
                )
            )
        rows.sort(key=lambda r: r.blast_radius_size, reverse=True)

        await self.audit_repo.log(
            action="blast_radius_dashboard_viewed",
            resource_type="service_dependency",
            resource_id=organization_id,
            user_id=user.id,
            details={"organization_id": organization_id, "services": len(services), "edges": len(edges)},
        )
        await self.session.commit()
        return BlastRadiusDashboard(
            total_services=len(services),
            total_dependencies=len(edges),
            has_cycles=g.has_cycle(),
            services=rows,
            highest_blast_radius=[r for r in rows if r.blast_radius_size > 0][:10],
        )

    # ----------------------------------------------------------- internals
    async def _resolve_origin_service(self, organization_id, incident) -> tuple[str | None, str]:
        # 1) On-call assignment carries the routed service.
        assignment = await self.assignment_repo.get_for_incident(incident.id, organization_id)
        if assignment is not None and assignment.service_name:
            return assignment.service_name, "assignment"
        # 2) The monitoring alert that created the incident.
        alerts, _ = await self.alert_repo.list_for_org(organization_id, limit=2000)
        for a in alerts:
            if a.incident_id == incident.id and a.service:
                return a.service, "monitoring_alert"
        return None, "unresolved"

    @staticmethod
    def _impact_level(origin, affected, severity) -> str:
        weight = _TIER_WEIGHT.get(origin.tier, 1)
        weight += sum(_TIER_WEIGHT.get(s.tier, 1) for s in affected)
        tier1 = (origin.tier == ServiceTier.TIER_1.value) or any(
            s.tier == ServiceTier.TIER_1.value for s in affected
        )
        n = len(affected)
        sev = (severity or "").upper()

        score = weight + n
        if sev in ("CRITICAL", "HIGH"):
            score += 3
        if tier1 and (n >= 3 or sev == "CRITICAL"):
            return "CRITICAL"
        if score >= 12 or (tier1 and n >= 1):
            return "HIGH"
        if score >= 6 or n >= 2:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _impact_text(level, n, tier_breakdown) -> str:
        t1 = tier_breakdown.get(ServiceTier.TIER_1.value, 0)
        base = {
            "CRITICAL": "Critical, customer-facing impact likely across multiple services.",
            "HIGH": "Significant impact to dependent services and likely customers.",
            "MEDIUM": "Moderate impact limited to a few dependent services.",
            "LOW": "Minimal impact; few or no downstream dependents.",
        }[level]
        extra = f" {t1} tier-1 service(s) in the blast radius." if t1 else ""
        return f"{base} {n} dependent service(s) affected.{extra}"

    @staticmethod
    def _ref(s) -> ServiceRef:
        return ServiceRef(id=s.id, name=s.name, tier=s.tier, owner_team=s.owner_team)

    @staticmethod
    def _edge(e, names: dict) -> DependencyEdge:
        return DependencyEdge(
            id=e.id,
            organization_id=e.organization_id,
            source_service_id=e.source_service_id,
            source_name=names.get(e.source_service_id),
            target_service_id=e.target_service_id,
            target_name=names.get(e.target_service_id),
            dependency_type=e.dependency_type,
            created_at=e.created_at,
        )
