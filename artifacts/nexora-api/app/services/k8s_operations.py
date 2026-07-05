"""Advanced Kubernetes Operations service (Sprint 65A).

Extends ControlPlaneService — does not duplicate cluster registration, approval,
or secret resolution.
"""

from __future__ import annotations

import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.control_plane.kubernetes import diagnostics as k8s_diagnostics
from app.control_plane.kubernetes import health as k8s_health
from app.control_plane.kubernetes import operations as k8s_ops
from app.control_plane.types import OPERATION_ACTION_MAP, OPERATION_EVENT_MAP
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.control_plane import K8sDiagnosticsBundle
from app.models.user import User
from app.platform.events import DomainEventType, emit_event
from app.repositories.audit import AuditLogRepository
from app.repositories.control_plane import (
    ClusterResourceRepository,
    ControlPlaneOperationRepository,
    KubernetesClusterRepository,
)
from app.schemas.control_plane import OperationCreate
from app.services.control_plane import ControlPlaneService
from app.tenancy.permissions import can_read_resources, can_write_resources

logger = get_logger(__name__)

_K8S_EVENT_TYPES = {
    "PodRestarted": DomainEventType.POD_RESTARTED,
    "DeploymentScaled": DomainEventType.DEPLOYMENT_SCALED,
    "RolloutStarted": DomainEventType.ROLLOUT_STARTED,
    "RolloutCompleted": DomainEventType.ROLLOUT_COMPLETED,
    "NodeDrained": DomainEventType.NODE_DRAINED,
    "NamespaceCreated": DomainEventType.NAMESPACE_CREATED,
    "PVCExpanded": DomainEventType.PVC_EXPANDED,
    "NetworkPolicyApplied": DomainEventType.NETWORK_POLICY_APPLIED,
    "DiagnosticsCollected": DomainEventType.DIAGNOSTICS_COLLECTED,
}


class K8sOperationsService:
    """Kubernetes operations platform — orchestrates Control Plane primitives."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.control_plane = ControlPlaneService(session)
        self.clusters = KubernetesClusterRepository(session)
        self.resources = ClusterResourceRepository(session)
        self.operations = ControlPlaneOperationRepository(session)
        self.audit = AuditLogRepository(session)

    def _ensure_read(self, user: User, org_context: OrgContext) -> str:
        if not can_read_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    def _ensure_write(self, user: User, org_context: OrgContext) -> str:
        if not can_write_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    async def _cluster_secret(self, user: User, org_context: OrgContext, cluster_id: str) -> tuple:
        organization_id = self._ensure_read(user, org_context)
        cluster = await self.clusters.get_for_org(cluster_id, organization_id)
        if not cluster:
            raise NotFoundError("Cluster", cluster_id)
        secret = await self.control_plane._resolve_secret(cluster.credential_id, user, org_context)
        return cluster, secret, organization_id

    async def read(
        self, user: User, org_context: OrgContext, cluster_id: str, action: str, params: dict,
    ) -> dict:
        _, secret, _ = await self._cluster_secret(user, org_context, cluster_id)
        start = time.perf_counter()
        try:
            result = await k8s_ops.execute_read(secret, action, params)
            self._record_read_metric(action, "success", time.perf_counter() - start)
            return result
        except Exception:
            self._record_read_metric(action, "failed", time.perf_counter() - start)
            raise

    async def overview(self, user: User, org_context: OrgContext, cluster_id: str) -> dict:
        organization_id = self._ensure_read(user, org_context)
        cluster = await self.clusters.get_for_org(cluster_id, organization_id)
        if not cluster:
            raise NotFoundError("Cluster", cluster_id)
        all_resources = await self.resources.list_for_cluster(organization_id, cluster_id)
        pods = [r for r in all_resources if r.kind == "Pod"]
        unhealthy = [p for p in pods if p.health != "HEALTHY"]
        ops = await self.operations.list_for_org(organization_id)
        pending = sum(1 for o in ops if o.cluster_id == cluster_id and o.status == "PENDING_APPROVAL")
        from sqlalchemy import select as sa_select
        from app.models.control_plane import ClusterPolicyFinding
        findings = list((await self.session.execute(
            sa_select(ClusterPolicyFinding).where(
                ClusterPolicyFinding.organization_id == organization_id,
                ClusterPolicyFinding.cluster_id == cluster_id,
            )
        )).scalars().all())
        health = k8s_health.compute_health_score(
            node_count=cluster.node_count,
            unhealthy_pods=len(unhealthy),
            total_pods=len(pods) or 1,
            pending_ops=pending,
            policy_findings=len(findings),
        )
        counts: dict[str, int] = {}
        for r in all_resources:
            counts[r.kind] = counts.get(r.kind, 0) + 1
        self._set_health_gauge(cluster_id, health["score"])
        self._set_resource_counts(cluster_id, counts)
        return {
            "cluster": {"id": cluster.id, "name": cluster.name, "health": cluster.health},
            "health_score": health,
            "resource_counts": counts,
            "pending_operations": pending,
        }

    async def collect_diagnostics(
        self, user: User, org_context: OrgContext, cluster_id: str,
        *, namespace: str, name: str, kind: str = "Pod",
    ) -> K8sDiagnosticsBundle:
        organization_id = self._ensure_read(user, org_context)
        cluster, secret, organization_id = await self._cluster_secret(user, org_context, cluster_id)
        inv = await self.resources.list_for_cluster(organization_id, cluster_id)
        inv_dicts = [{"kind": r.kind, "namespace": r.namespace, "name": r.name, "health": r.health} for r in inv]
        recent_ops = [
            {"kind": o.kind, "status": o.status, "resource": o.resource_name}
            for o in await self.operations.list_for_org(organization_id)
            if o.cluster_id == cluster_id
        ][:10]
        bundle_data = await k8s_diagnostics.collect_diagnostics_bundle(
            secret, namespace=namespace, name=name, kind=kind,
            cluster_resources=inv_dicts, recent_operations=recent_ops,
        )
        row = K8sDiagnosticsBundle(
            organization_id=organization_id,
            cluster_id=cluster.id,
            namespace=namespace,
            resource_kind=kind,
            resource_name=name,
            bundle=bundle_data,
            collected_by=user.id,
        )
        self.session.add(row)
        await self.session.flush()
        await emit_event(
            self.session, DomainEventType.DIAGNOSTICS_COLLECTED,
            organization_id=organization_id,
            aggregate_type="k8s_diagnostics",
            aggregate_id=row.id,
            payload={"cluster_id": cluster_id, "kind": kind, "name": name, "namespace": namespace},
        )
        await self.audit.log(
            action="k8s.diagnostics_collected", resource_type="cp_k8s_diagnostics",
            resource_id=row.id, user_id=user.id,
        )
        return row

    async def list_diagnostics(
        self, user: User, org_context: OrgContext, cluster_id: str,
    ) -> list[K8sDiagnosticsBundle]:
        organization_id = self._ensure_read(user, org_context)
        stmt = (
            select(K8sDiagnosticsBundle)
            .where(K8sDiagnosticsBundle.organization_id == organization_id,
                   K8sDiagnosticsBundle.cluster_id == cluster_id)
            .order_by(K8sDiagnosticsBundle.created_at.desc())
            .limit(50)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def propose(
        self, user: User, org_context: OrgContext, payload: OperationCreate,
    ):
        """Delegate to Control Plane approval workflow."""
        return await self.control_plane.propose_operation(user, org_context, payload)

    async def decide(self, user: User, org_context: OrgContext, operation_id: str, approved: bool):
        return await self.control_plane.decide_operation(user, org_context, operation_id, approved)

    async def execute(self, user: User, org_context: OrgContext, operation_id: str):
        organization_id = self._ensure_write(user, org_context)
        op = await self.control_plane.operations.get_by_id(operation_id)
        if not op or op.organization_id != organization_id:
            raise NotFoundError("Operation", operation_id)
        start = time.perf_counter()
        result_op = await self._execute_with_metrics(user, org_context, operation_id)
        duration = time.perf_counter() - start
        self._record_operation_metric(op.kind, result_op.status, duration)
        event_name = OPERATION_EVENT_MAP.get(op.kind)
        if event_name and result_op.status == "SUCCEEDED":
            event_type = _K8S_EVENT_TYPES.get(event_name)
            if event_type:
                await emit_event(
                    self.session, event_type,
                    organization_id=organization_id,
                    aggregate_type="cp_operation",
                    aggregate_id=op.id,
                    payload={"kind": op.kind, "cluster_id": op.cluster_id},
                )
        return result_op

    async def _execute_with_metrics(self, user, org_context, operation_id):
        return await self.control_plane.execute_operation(user, org_context, operation_id)

    def _record_read_metric(self, action: str, status: str, duration: float) -> None:
        try:
            from app.observability import metrics
            metrics.record_k8s_operation("read", action, status, duration)
        except Exception:  # noqa: BLE001
            pass

    def _record_operation_metric(self, kind: str, status: str, duration: float) -> None:
        try:
            from app.observability import metrics
            metrics.record_k8s_operation("write", kind, status, duration)
        except Exception:  # noqa: BLE001
            pass

    def _set_health_gauge(self, cluster_id: str, score: int) -> None:
        try:
            from app.observability import metrics
            metrics.set_k8s_cluster_health(cluster_id, score)
        except Exception:  # noqa: BLE001
            pass

    def _set_resource_counts(self, cluster_id: str, counts: dict) -> None:
        try:
            from app.observability import metrics
            for kind, count in counts.items():
                metrics.set_k8s_resource_count(cluster_id, kind, count)
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def supported_read_actions() -> list[str]:
        return sorted({
            "logs", "previous_logs", "describe", "get_yaml", "events",
            "rollout_status", "rollout_history", "revision_diff",
            "top_pods", "top_nodes", "namespace_detail", "storage_analysis",
            "ingress_validation", "cert_status",
            "list_pods", "list_deployments", "list_statefulsets", "list_daemonsets",
            "list_replicasets", "list_jobs", "list_cronjobs", "list_namespaces",
            "list_pvc", "list_pv", "list_storageclasses", "list_services",
            "list_ingress", "list_network_policies", "list_nodes",
        })

    @staticmethod
    def supported_write_kinds() -> list[str]:
        return sorted(OPERATION_ACTION_MAP.keys())
