"""Sprint 46B - Architecture Discovery & Service Map Engine.

Builds a read-only topology map of the organization from connected platform
signals (no cloud-control-plane mutations, no infra changes):

* Service catalog (42C)        -> SERVICE / DATABASE / LOAD_BALANCER nodes
* Service dependencies (44B)   -> typed edges (DEPENDS_ON / STORES_IN / ROUTES_TO)
* Monitoring alerts (42A)      -> KUBERNETES_WORKLOAD / CLOUD_RESOURCE nodes,
                                   monitoring coverage, services seen only in alerts
* Deployment runs              -> CLOUD_RESOURCE / KUBERNETES_WORKLOAD + REPOSITORY
                                   nodes with DEPLOYS_TO edges
* Capacity metrics (43A)       -> KUBERNETES_WORKLOAD (cluster) nodes + RUNS_ON
* SLOs (42C)                   -> SLO coverage flags

It then analyses the graph for orphan services, single points of failure,
missing monitoring, and missing SLO coverage, and persists an immutable snapshot.
The same node/edge model is the plug-in point for live K8s/AWS/Azure SDK readers.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NexoraException
from app.models.architecture import EdgeRelationship, NodeType
from app.repositories.architecture import (
    ArchitectureEdgeRepository,
    ArchitectureNodeRepository,
    ArchitectureSnapshotRepository,
)
from app.repositories.audit import AuditLogRepository
from app.repositories.capacity import CapacityMetricRepository
from app.repositories.deployment import DeploymentRunRepository
from app.repositories.incident import MonitoringAlertRepository
from app.repositories.slo import ServiceRepository, ServiceSLORepository
from app.schemas.architecture import (
    ArchitectureDashboard,
    ArchitectureTrendPoint,
    EdgeView,
    NodeView,
    RiskAreas,
    SnapshotResponse,
)
from app.services.graph import GraphService
from app.tenancy.permissions import can_read_ai_teams

logger = structlog.get_logger(__name__)

_DB_TOKENS = {"postgres", "postgresql", "mysql", "mariadb", "mongo", "mongodb", "redis",
              "memcached", "cache", "kafka", "rabbitmq", "rabbit", "queue", "dynamo",
              "dynamodb", "cassandra", "elasticsearch", "elastic", "sql", "db", "database",
              "datastore", "warehouse", "snowflake", "bigquery"}
_LB_TOKENS = {"gateway", "ingress", "loadbalancer", "balancer", "nginx", "envoy", "traefik",
              "haproxy", "alb", "nlb", "elb", "proxy", "cdn", "apigateway", "lb"}
_CLOUD_PROVIDERS = {"AWS", "AZURE", "GCP", "CLOUDWATCH"}


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt):
    if dt is None:
        return None
    return dt if getattr(dt, "tzinfo", None) else dt.replace(tzinfo=UTC)


def _tokens(name: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", (name or "").lower()) if t}


def _classify(name: str) -> str:
    toks = _tokens(name)
    if toks & _LB_TOKENS:
        return NodeType.LOAD_BALANCER.value
    if toks & _DB_TOKENS:
        return NodeType.DATABASE.value
    return NodeType.SERVICE.value


_PREFIX = {
    NodeType.SERVICE.value: "service",
    NodeType.DATABASE.value: "database",
    NodeType.LOAD_BALANCER.value: "lb",
    NodeType.KUBERNETES_WORKLOAD.value: "k8s",
    NodeType.CLOUD_RESOURCE.value: "cloud",
    NodeType.REPOSITORY.value: "repo",
}


class ArchitectureDiscoveryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit_repo = AuditLogRepository(session)
        self.snapshot_repo = ArchitectureSnapshotRepository(session)
        self.node_repo = ArchitectureNodeRepository(session)
        self.edge_repo = ArchitectureEdgeRepository(session)
        self.service_repo = ServiceRepository(session)
        self.slo_repo = ServiceSLORepository(session)
        self.graph = GraphService(session)
        self.alert_repo = MonitoringAlertRepository(session)
        self.run_repo = DeploymentRunRepository(session)
        self.metric_repo = CapacityMetricRepository(session)

    def _ensure_read(self, user, org_context) -> None:
        if not user.is_superuser and (
            not org_context.role or not can_read_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    # --------------------------------------------------------------- public
    async def discover(self, user, org_context) -> SnapshotResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)

        nodes, edges = await self._build_graph(organization_id)
        self._analyze(nodes, edges)

        type_counts: dict[str, int] = defaultdict(int)
        for n in nodes.values():
            type_counts[n["node_type"]] += 1

        risk = RiskAreas(
            orphan_services=[n["name"] for n in nodes.values() if n["is_orphan"]],
            single_points_of_failure=[n["name"] for n in nodes.values() if n["is_spof"]],
            missing_monitoring=[n["name"] for n in nodes.values()
                                if n["node_type"] in (NodeType.SERVICE.value, NodeType.DATABASE.value)
                                and not n["has_monitoring"]],
            missing_slo=[n["name"] for n in nodes.values()
                         if n["node_type"] == NodeType.SERVICE.value and not n["has_slo"]],
        )
        summary = (
            f"Discovered {len(nodes)} node(s) and {len(edges)} relationship(s): "
            + ", ".join(f"{c} {t.lower()}" for t, c in sorted(type_counts.items())) + ". "
            + f"{len(risk.single_points_of_failure)} single point(s) of failure, "
            + f"{len(risk.orphan_services)} orphan(s), "
            + f"{len(risk.missing_monitoring)} missing monitoring, "
            + f"{len(risk.missing_slo)} missing SLO coverage."
        )

        snapshot = await self.snapshot_repo.create(
            organization_id=organization_id,
            node_count=len(nodes),
            edge_count=len(edges),
            orphan_count=len(risk.orphan_services),
            spof_count=len(risk.single_points_of_failure),
            missing_monitoring_count=len(risk.missing_monitoring),
            missing_slo_count=len(risk.missing_slo),
            summary=summary,
            details={"node_type_counts": dict(type_counts), "risk_areas": risk.model_dump()},
            created_by=user.id,
        )
        for n in nodes.values():
            await self.node_repo.create(
                snapshot_id=snapshot.id,
                organization_id=organization_id,
                node_key=n["node_key"],
                node_type=n["node_type"],
                name=n["name"],
                provider=n.get("provider"),
                environment=n.get("environment"),
                service_name=n.get("service_name"),
                has_monitoring=n["has_monitoring"],
                has_slo=n["has_slo"],
                is_orphan=n["is_orphan"],
                is_spof=n["is_spof"],
                dependents_count=n["dependents_count"],
                depends_on_count=n["depends_on_count"],
                node_metadata=n.get("metadata") or {},
            )
        for e in edges:
            await self.edge_repo.create(
                snapshot_id=snapshot.id,
                organization_id=organization_id,
                source_key=e[0],
                target_key=e[1],
                relationship_type=e[2],
            )

        await self.audit_repo.log(
            action="architecture_discovered",
            resource_type="architecture_snapshot",
            resource_id=snapshot.id,
            user_id=user.id,
            details={"organization_id": organization_id, "nodes": len(nodes), "edges": len(edges)},
        )
        await self.session.commit()
        return self._response_from_built(snapshot, nodes, edges, type_counts, risk)

    async def list(self, user, org_context):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        return await self.snapshot_repo.list_for_org(organization_id)

    async def get(self, user, org_context, snapshot_id: str) -> SnapshotResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        snapshot = await self.snapshot_repo.get_for_org(snapshot_id, organization_id)
        if snapshot is None:
            raise NexoraException("Architecture snapshot not found.", status_code=404)
        return await self._response_from_rows(snapshot, organization_id)

    async def dashboard(self, user, org_context) -> ArchitectureDashboard:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        snapshots = await self.snapshot_repo.list_for_org(organization_id, limit=100)
        latest_resp = None
        if snapshots:
            latest_resp = await self._response_from_rows(snapshots[0], organization_id)
        trend = [
            ArchitectureTrendPoint(
                date=_aware(s.created_at).strftime("%Y-%m-%d %H:%M"),
                node_count=s.node_count, edge_count=s.edge_count,
                spof_count=s.spof_count, missing_monitoring_count=s.missing_monitoring_count,
            )
            for s in reversed(snapshots)
        ]
        await self.audit_repo.log(
            action="architecture_dashboard_viewed",
            resource_type="architecture_snapshot",
            resource_id=None,
            user_id=user.id,
            details={"organization_id": organization_id, "snapshots": len(snapshots)},
        )
        await self.session.commit()
        return ArchitectureDashboard(latest=latest_resp, snapshots_count=len(snapshots), trend=trend)

    # --------------------------------------------------------- graph builder
    def _node(self, nodes, key, node_type, name, *, provider=None, environment=None,
              service_name=None, metadata=None):
        if key not in nodes:
            nodes[key] = {
                "node_key": key, "node_type": node_type, "name": name,
                "provider": provider, "environment": environment, "service_name": service_name,
                "has_monitoring": False, "has_slo": False, "is_orphan": False, "is_spof": False,
                "dependents_count": 0, "depends_on_count": 0, "metadata": metadata or {},
            }
        return nodes[key]

    async def _build_graph(self, organization_id):
        nodes: dict[str, dict] = {}
        edges: set[tuple] = set()

        # --- service catalog (42C) -> SERVICE/DATABASE/LOAD_BALANCER ---------
        services = await self.service_repo.list_for_org(organization_id)
        name_to_key: dict[str, str] = {}
        id_to_name: dict[str, str] = {}
        for svc in services:
            ntype = _classify(svc.name)
            key = f"{_PREFIX[ntype]}:{svc.name}"
            node = self._node(nodes, key, ntype, svc.name, service_name=svc.name,
                              metadata={"tier": svc.tier, "owner_team": svc.owner_team})
            name_to_key[svc.name] = key
            id_to_name[svc.id] = svc.name
            slos = await self.slo_repo.list_for_service(svc.id, organization_id)
            node["has_slo"] = bool(slos)

        # --- service dependencies (44B) -> typed edges -----------------------
        deps = await self.graph.list_service_edges(organization_id)
        rel_map = {"DATASTORE": EdgeRelationship.STORES_IN.value,
                   "NETWORK": EdgeRelationship.ROUTES_TO.value}
        for d in deps:
            sname = id_to_name.get(d.source_service_id)
            tname = id_to_name.get(d.target_service_id)
            if not sname or not tname:
                continue
            src = name_to_key.get(sname)
            tgt = name_to_key.get(tname)
            if not src or not tgt:
                continue
            rel = rel_map.get(d.dependency_type, EdgeRelationship.DEPENDS_ON.value)
            # If the target is a database node, storing semantics win.
            if nodes[tgt]["node_type"] == NodeType.DATABASE.value:
                rel = EdgeRelationship.STORES_IN.value
            edges.add((src, tgt, rel))

        # --- monitoring (42A) -> infra nodes + coverage ----------------------
        alerts, _ = await self.alert_repo.list_for_org(organization_id, limit=2000)
        for a in alerts:
            svc_key = None
            if a.service:
                # Discover services that exist only in monitoring.
                if a.service not in name_to_key:
                    ntype = _classify(a.service)
                    svc_key = f"{_PREFIX[ntype]}:{a.service}"
                    self._node(nodes, svc_key, ntype, a.service, service_name=a.service)
                    name_to_key[a.service] = svc_key
                else:
                    svc_key = name_to_key[a.service]
                nodes[svc_key]["has_monitoring"] = True
            prov = (a.provider or "").upper()
            env = a.environment
            infra_key = None
            if prov == "KUBERNETES":
                infra_key = f"k8s:{env or 'cluster'}"
                self._node(nodes, infra_key, NodeType.KUBERNETES_WORKLOAD.value,
                           f"k8s/{env or 'cluster'}", provider="KUBERNETES", environment=env)
            elif prov in _CLOUD_PROVIDERS:
                infra_key = f"cloud:{prov}:{env or 'default'}"
                self._node(nodes, infra_key, NodeType.CLOUD_RESOURCE.value,
                           f"{prov} ({env or 'default'})", provider=prov, environment=env)
            if svc_key and infra_key:
                edges.add((svc_key, infra_key, EdgeRelationship.RUNS_ON.value))

        # --- deployment runs -> cloud/k8s + repository -----------------------
        runs, _ = await self.run_repo.list_by_organization(organization_id, limit=2000)
        for r in runs:
            prov = (r.deployment_provider or "").upper()
            env = r.environment
            target_key = None
            if prov == "KUBERNETES":
                target_key = f"k8s:{env or 'cluster'}"
                self._node(nodes, target_key, NodeType.KUBERNETES_WORKLOAD.value,
                           f"k8s/{env or 'cluster'}", provider="KUBERNETES", environment=env)
            elif prov in _CLOUD_PROVIDERS or prov == "VM":
                pkey = prov or "VM"
                target_key = f"cloud:{pkey}:{env or 'default'}"
                self._node(nodes, target_key, NodeType.CLOUD_RESOURCE.value,
                           f"{pkey} ({env or 'default'})", provider=pkey, environment=env)
            if r.project_id:
                repo_key = f"repo:{r.project_id[:8]}"
                self._node(nodes, repo_key, NodeType.REPOSITORY.value,
                           f"repo {r.project_id[:8]}", metadata={"project_id": r.project_id})
                if target_key:
                    edges.add((repo_key, target_key, EdgeRelationship.DEPLOYS_TO.value))

        # --- capacity metrics (43A) -> k8s clusters + RUNS_ON ----------------
        metrics = await self.metric_repo.query(organization_id)
        for mt in metrics:
            if not mt.cluster:
                continue
            ck = f"k8s:{mt.cluster}"
            self._node(nodes, ck, NodeType.KUBERNETES_WORKLOAD.value, f"k8s/{mt.cluster}",
                       provider="KUBERNETES", environment=mt.environment)
            if mt.service and mt.service in name_to_key:
                edges.add((name_to_key[mt.service], ck, EdgeRelationship.RUNS_ON.value))

        return nodes, edges

    # ------------------------------------------------------------- analysis
    @staticmethod
    def _analyze(nodes: dict, edges: set):
        out_deg: dict[str, int] = defaultdict(int)
        in_deg: dict[str, int] = defaultdict(int)
        in_sources: dict[str, set] = defaultdict(set)
        for src, tgt, _rel in edges:
            out_deg[src] += 1
            in_deg[tgt] += 1
            in_sources[tgt].add(src)
        for key, n in nodes.items():
            n["depends_on_count"] = out_deg.get(key, 0)
            n["dependents_count"] = len(in_sources.get(key, set()))
            degree = out_deg.get(key, 0) + in_deg.get(key, 0)
            # Orphans: relevant entities with no relationships at all.
            n["is_orphan"] = degree == 0 and n["node_type"] in (
                NodeType.SERVICE.value, NodeType.DATABASE.value, NodeType.LOAD_BALANCER.value
            )
            # SPOF: two or more distinct entities depend on this single node.
            n["is_spof"] = n["dependents_count"] >= 2

    # ------------------------------------------------------------- shaping
    @staticmethod
    def _node_view(n: dict) -> NodeView:
        return NodeView(
            node_key=n["node_key"], node_type=n["node_type"], name=n["name"],
            provider=n.get("provider"), environment=n.get("environment"),
            service_name=n.get("service_name"), has_monitoring=n["has_monitoring"],
            has_slo=n["has_slo"], is_orphan=n["is_orphan"], is_spof=n["is_spof"],
            dependents_count=n["dependents_count"], depends_on_count=n["depends_on_count"],
            metadata=n.get("metadata") or {},
        )

    def _response_from_built(self, snapshot, nodes, edges, type_counts, risk) -> SnapshotResponse:
        return SnapshotResponse(
            id=snapshot.id, organization_id=snapshot.organization_id,
            node_count=snapshot.node_count, edge_count=snapshot.edge_count,
            orphan_count=snapshot.orphan_count, spof_count=snapshot.spof_count,
            missing_monitoring_count=snapshot.missing_monitoring_count,
            missing_slo_count=snapshot.missing_slo_count, summary=snapshot.summary,
            nodes=[self._node_view(n) for n in nodes.values()],
            edges=[EdgeView(source=e[0], target=e[1], relationship=e[2]) for e in edges],
            risk_areas=risk, node_type_counts=dict(type_counts),
            created_at=snapshot.created_at,
        )

    async def _response_from_rows(self, snapshot, organization_id) -> SnapshotResponse:
        node_rows = await self.node_repo.list_for_snapshot(snapshot.id, organization_id)
        edge_rows = await self.edge_repo.list_for_snapshot(snapshot.id, organization_id)
        details = snapshot.details or {}
        risk = RiskAreas(**(details.get("risk_areas") or {}))
        return SnapshotResponse(
            id=snapshot.id, organization_id=snapshot.organization_id,
            node_count=snapshot.node_count, edge_count=snapshot.edge_count,
            orphan_count=snapshot.orphan_count, spof_count=snapshot.spof_count,
            missing_monitoring_count=snapshot.missing_monitoring_count,
            missing_slo_count=snapshot.missing_slo_count, summary=snapshot.summary,
            nodes=[
                NodeView(
                    node_key=r.node_key, node_type=r.node_type, name=r.name, provider=r.provider,
                    environment=r.environment, service_name=r.service_name,
                    has_monitoring=r.has_monitoring, has_slo=r.has_slo, is_orphan=r.is_orphan,
                    is_spof=r.is_spof, dependents_count=r.dependents_count,
                    depends_on_count=r.depends_on_count, metadata=r.node_metadata or {},
                )
                for r in node_rows
            ],
            edges=[EdgeView(source=r.source_key, target=r.target_key, relationship=r.relationship_type)
                   for r in edge_rows],
            risk_areas=risk, node_type_counts=details.get("node_type_counts", {}),
            created_at=snapshot.created_at,
        )
