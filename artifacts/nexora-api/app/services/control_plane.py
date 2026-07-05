"""Multi-cloud & Kubernetes control plane orchestration."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.control_plane.cloud.registry import get_cloud_provider, supported_cloud_providers
from app.control_plane.kubernetes import discovery as k8s_discovery
from app.control_plane.kubernetes import gitops as gitops_mod
from app.control_plane.kubernetes import helm as helm_mod
from app.control_plane.kubernetes import operations as k8s_ops
from app.control_plane.kubernetes.policies import scan_policies
from app.control_plane.kubernetes.registry import get_cluster_provider, supported_distributions
from app.control_plane.types import DESTRUCTIVE_OPERATIONS, OPERATION_ACTION_MAP, OperationKind, OperationStatus
from app.integration_readiness.live_gate import CONTROL_PLANE_CAPABILITIES, LiveMutationGate
from app.integration_readiness.preflight import make_idempotency_key
from app.core.exceptions import ForbiddenError, NexoraException, NotFoundError
from app.core.logging import get_logger
from app.models.control_plane import (
    CloudAccount,
    CloudSyncRun,
    ClusterDiscoveryRun,
    ClusterPolicyFinding,
    ControlPlaneCostSnapshot,
    ControlPlaneOperation,
    KubernetesCluster,
)
from app.models.user import User
from app.platform.events import DomainEventType, emit_event
from app.repositories.audit import AuditLogRepository
from app.repositories.control_plane import (
    CloudAccountRepository,
    CloudInventoryRepository,
    ClusterResourceRepository,
    ControlPlaneOperationRepository,
    KubernetesClusterRepository,
)
from app.repositories.credential import DeploymentCredentialRepository
from app.security.secrets import SecretManagerService
from app.tenancy.permissions import can_read_resources, can_write_resources

logger = get_logger(__name__)

_PROVIDER_MAP = {
    "AWS": "AWS", "AZURE": "AZURE", "GCP": "GCP",
    "DIGITALOCEAN": "DIGITALOCEAN", "ORACLE": "ORACLE", "VMWARE": "VMWARE",
}


class ControlPlaneService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.cloud_accounts = CloudAccountRepository(session)
        self.clusters = KubernetesClusterRepository(session)
        self.operations = ControlPlaneOperationRepository(session)
        self.cluster_resources = ClusterResourceRepository(session)
        self.cloud_inventory = CloudInventoryRepository(session)
        self.credentials = DeploymentCredentialRepository(session)
        self.secrets = SecretManagerService(session)
        self.audit = AuditLogRepository(session)

    def _ensure_read(self, user: User, org_context: OrgContext) -> None:
        if not can_read_resources(org_context.role):
            raise ForbiddenError("Insufficient permissions")

    def _ensure_write(self, user: User, org_context: OrgContext) -> None:
        if not can_write_resources(org_context.role):
            raise ForbiddenError("Insufficient permissions")

    async def _resolve_secret(self, credential_id: str, user: User, org_context: OrgContext) -> dict:
        _cred, secret = await self.secrets.resolve_secret(
            credential_id, user=user, org_context=org_context, reason="control plane",
        )
        return secret

    # ---------------------------------------------------------- cloud accounts
    async def register_cloud_account(
        self, user: User, org_context: OrgContext, credential_id: str, display_name: str | None,
    ) -> CloudAccount:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        cred = await self.credentials.get_for_org(credential_id, organization_id)
        if not cred:
            raise NotFoundError("Credential", credential_id)
        provider_key = _PROVIDER_MAP.get(cred.provider.upper())
        if not provider_key:
            raise NexoraException(f"Provider {cred.provider} is not a supported cloud provider", 400)
        secret = await self._resolve_secret(credential_id, user, org_context)
        impl = get_cloud_provider(provider_key)
        conn = await asyncio.to_thread(impl.test_connection, secret)
        account = await self.cloud_accounts.create(
            organization_id=organization_id,
            credential_id=credential_id,
            provider=provider_key,
            account_id=conn.account_id,
            display_name=display_name or conn.display_name,
            regions=conn.regions,
            health=conn.health,
            permissions=[p if isinstance(p, dict) else {"name": str(p)} for p in conn.permissions],
            created_by=user.id,
        )
        await self.audit.log(
            action="cloud_account_registered", resource_type="cloud_account", resource_id=account.id,
            user_id=user.id, details={"provider": provider_key, "organization_id": organization_id},
        )
        return account

    async def list_cloud_accounts(self, user: User, org_context: OrgContext) -> list[CloudAccount]:
        self._ensure_read(user, org_context)
        return await self.cloud_accounts.list_for_org(org_context.requires_organization)

    async def sync_cloud_account(self, user: User, org_context: OrgContext, account_id: str) -> CloudSyncRun:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        account = await self.cloud_accounts.get_by_id(account_id)
        if not account or account.organization_id != organization_id:
            raise NotFoundError("CloudAccount", account_id)
        run = CloudSyncRun(
            organization_id=organization_id, cloud_account_id=account_id, status="RUNNING",
        )
        self.session.add(run)
        await self.session.flush()
        secret = await self._resolve_secret(account.credential_id, user, org_context)
        impl = get_cloud_provider(account.provider)
        inventory = await asyncio.to_thread(impl.list_inventory, secret, regions=account.regions)
        cost = await asyncio.to_thread(impl.estimate_costs, secret, inventory)
        rows = [{
            "provider": i.provider, "account": i.account, "region": i.region,
            "resource_id": i.resource_id, "resource_type": i.resource_type,
            "resource_name": i.resource_name, "tags": i.tags, "health": i.health,
            "owner": i.owner, "environment": (i.tags or {}).get("environment"),
            "resource_meta": i.metadata,
        } for i in inventory]
        await self.cloud_inventory.replace_for_account(organization_id, account_id, rows)
        account.resource_count = len(rows)
        account.cost_summary = {
            "currency": cost.currency, "total_estimate": cost.total_estimate,
            "by_service": cost.by_service, "idle_estimate": cost.idle_estimate,
        }
        account.last_sync_at = datetime.now(UTC)
        account.last_sync_status = "SUCCEEDED"
        run.status = "SUCCEEDED"
        run.resources_total = len(rows)
        run.resources_added = len(rows)
        run.finished_at = datetime.now(UTC)
        await emit_event(
            self.session, DomainEventType.DISCOVERY_FINISHED,
            organization_id=organization_id,
            payload={"scope": "cloud", "account_id": account_id, "resources": len(rows)},
        )
        return run

    # -------------------------------------------------------------- clusters
    async def register_cluster(
        self, user: User, org_context: OrgContext, credential_id: str, name: str,
        distribution: str, cloud_account_id: str | None,
    ) -> KubernetesCluster:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        cred = await self.credentials.get_for_org(credential_id, organization_id)
        if not cred or cred.provider.upper() not in ("KUBERNETES", "AWS", "AZURE", "GCP"):
            raise NexoraException("Cluster registration requires a Kubernetes or cloud credential", 400)
        secret = await self._resolve_secret(credential_id, user, org_context)
        if cred.provider.upper() != "KUBERNETES":
            secret = secret if secret.get("kubeconfig") else {"kubeconfig": ""}
        impl = get_cluster_provider(distribution)
        info = await asyncio.to_thread(impl.connect, secret)
        cluster = await self.clusters.create(
            organization_id=organization_id, credential_id=credential_id,
            cloud_account_id=cloud_account_id, name=name, distribution=distribution.upper(),
            version=info.version, api_endpoint=info.api_endpoint, health=info.health,
            node_count=info.node_count, namespace_count=info.namespace_count, created_by=user.id,
        )
        await self.audit.log(
            action="cluster_registered", resource_type="kubernetes_cluster", resource_id=cluster.id,
            user_id=user.id, details={"name": name, "distribution": distribution},
        )
        return cluster

    async def list_clusters(self, user: User, org_context: OrgContext) -> list[KubernetesCluster]:
        self._ensure_read(user, org_context)
        return await self.clusters.list_for_org(org_context.requires_organization)

    async def get_cluster(
        self, user: User, org_context: OrgContext, cluster_id: str,
    ) -> KubernetesCluster:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        cluster = await self.clusters.get_for_org(cluster_id, organization_id)
        if not cluster:
            raise NotFoundError("Cluster", cluster_id)
        return cluster

    async def discover_cluster(self, user: User, org_context: OrgContext, cluster_id: str) -> ClusterDiscoveryRun:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        cluster = await self.clusters.get_for_org(cluster_id, organization_id)
        if not cluster:
            raise NotFoundError("Cluster", cluster_id)
        run = ClusterDiscoveryRun(
            organization_id=organization_id, cluster_id=cluster_id, status="RUNNING",
        )
        self.session.add(run)
        await self.session.flush()
        secret = await self._resolve_secret(cluster.credential_id, user, org_context)
        resources = await k8s_discovery.discover_cluster(secret, cluster_name=cluster.name)
        rows = [{
            "kind": r.kind, "namespace": r.namespace, "name": r.name, "uid": r.uid,
            "labels": r.labels, "annotations": r.annotations, "health": r.health,
            "resource_meta": r.metadata,
        } for r in resources]
        await self.cluster_resources.replace_for_cluster(organization_id, cluster_id, rows)
        cluster.last_discovery_at = datetime.now(UTC)
        cluster.node_count = sum(1 for r in resources if r.kind == "Node")
        cluster.namespace_count = sum(1 for r in resources if r.kind == "Namespace")
        run.resource_count = len(rows)
        run.status = "SUCCEEDED"
        run.finished_at = datetime.now(UTC)
        # Policy scan
        findings = scan_policies(resources)
        from sqlalchemy import delete, select

        await self.session.execute(
            delete(ClusterPolicyFinding).where(
                ClusterPolicyFinding.cluster_id == cluster_id,
                ClusterPolicyFinding.organization_id == organization_id,
            )
        )
        for f in findings:
            self.session.add(ClusterPolicyFinding(
                organization_id=organization_id, cluster_id=cluster_id,
                policy=f.policy, severity=f.severity, resource_kind=f.resource_kind,
                resource_name=f.resource_name, namespace=f.namespace,
                message=f.message, recommendation=f.recommendation,
            ))
        await emit_event(
            self.session, DomainEventType.DISCOVERY_FINISHED,
            organization_id=organization_id,
            payload={"scope": "cluster", "cluster_id": cluster_id, "resources": len(rows)},
        )
        return run

    async def list_cluster_resources(
        self, user: User, org_context: OrgContext, cluster_id: str,
        *, kind: str | None = None, namespace: str | None = None,
    ):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        if not await self.clusters.get_for_org(cluster_id, organization_id):
            raise NotFoundError("Cluster", cluster_id)
        return await self.cluster_resources.list_for_cluster(
            organization_id, cluster_id, kind=kind, namespace=namespace,
        )

    # ------------------------------------------------------------- operations
    async def propose_operation(
        self, user: User, org_context: OrgContext, data,
    ) -> ControlPlaneOperation:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        kind = OperationKind(data.kind)
        cluster = await self.clusters.get_for_org(data.cluster_id, organization_id)
        if not cluster:
            raise NotFoundError("Cluster", data.cluster_id)
        op = await self.operations.create(
            organization_id=organization_id, cluster_id=data.cluster_id, kind=kind.value,
            status=OperationStatus.PENDING_APPROVAL.value,
            namespace=data.namespace, resource_name=data.resource_name,
            params=data.params, requested_by=user.id,
        )
        await self.audit.log(
            action="control_plane_operation_proposed", resource_type="cp_operation",
            resource_id=op.id, user_id=user.id,
            details={"kind": kind.value, "cluster_id": data.cluster_id},
        )
        return op

    async def decide_operation(
        self, user: User, org_context: OrgContext, operation_id: str, approved: bool,
    ) -> ControlPlaneOperation:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        op = await self.operations.get_by_id(operation_id)
        if not op or op.organization_id != organization_id:
            raise NotFoundError("Operation", operation_id)
        if op.status != OperationStatus.PENDING_APPROVAL.value:
            raise NexoraException("Operation already decided", 409)
        if approved:
            op.status = OperationStatus.APPROVED.value
            op.approved_by = user.id
            op.approved_at = datetime.now(UTC)
        else:
            op.status = OperationStatus.REJECTED.value
        await self.audit.log(
            action="control_plane_operation_decided", resource_type="cp_operation",
            resource_id=op.id, user_id=user.id, details={"approved": approved},
        )
        return op

    async def execute_operation(
        self, user: User, org_context: OrgContext, operation_id: str,
    ) -> ControlPlaneOperation:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        op = await self.operations.get_by_id(operation_id)
        if not op or op.organization_id != organization_id:
            raise NotFoundError("Operation", operation_id)
        if op.status != OperationStatus.APPROVED.value:
            raise NexoraException("Operation must be approved before execution", 400)
        cluster = await self.clusters.get_for_org(op.cluster_id, organization_id)
        if not cluster:
            raise NotFoundError("Cluster", op.cluster_id or "")
        params = dict(op.params or {})
        params.setdefault("namespace", op.namespace)
        params.setdefault("name", op.resource_name)
        explicit_simulation = bool(params.get("explicit_simulation"))
        action_map = dict(OPERATION_ACTION_MAP)
        action = action_map.get(op.kind, op.kind.lower())
        gate = LiveMutationGate(self.session)
        reg = await gate.ensure_registry(
            organization_id=organization_id,
            resource_type="kubernetes",
            resource_id=cluster.id,
            provider_type="KUBERNETES",
            credential_id=cluster.credential_id,
        )
        preflight = await gate.preflight_mutation(
            organization_id=organization_id,
            actor_id=user.id,
            integration_connection_id=reg.id,
            operation_type=f"control_plane.{action}",
            resource_type="cp_operation",
            resource_id=op.id,
            idempotency_key=make_idempotency_key(org_id=organization_id, operation=action, target_id=op.id),
            required_capabilities=CONTROL_PLANE_CAPABILITIES.get(action, ["kubernetes.workloads.write"]),
            approval_satisfied=True,
            explicit_simulation=explicit_simulation,
            credential_id=cluster.credential_id,
            resource_lookup=("kubernetes", cluster.id),
        )
        if not preflight["allowed"]:
            op.status = OperationStatus.FAILED.value
            op.error = (preflight.get("reason") or "Preflight blocked")[:500]
            op.result = {"blocked": True, "integration_readiness": preflight.get("evidence_context")}
            await self.audit.log(
                action="control_plane_operation_blocked", resource_type="cp_operation",
                resource_id=op.id, user_id=user.id,
                details={"reason_code": preflight.get("reason_code")},
            )
            return op
        op.status = OperationStatus.EXECUTING.value
        correlation_id = preflight["correlation_id"]
        await gate.record_execution(
            organization_id=organization_id,
            actor_id=user.id,
            connection_id=preflight.get("connection_id"),
            operation_type=f"control_plane.{action}",
            resource_id=op.id,
            correlation_id=correlation_id,
            outcome="started",
        )
        secret = {} if preflight.get("simulated") else await self._resolve_secret(cluster.credential_id, user, org_context)
        try:
            result = await k8s_ops.execute_write(
                secret, action, params, explicit_simulation=preflight.get("simulated", False),
            )
            if result.get("blocked"):
                op.status = OperationStatus.FAILED.value
                op.error = result.get("message", "Live execution blocked")[:500]
                op.result = {**result, "integration_readiness": preflight.get("evidence_context")}
                await gate.record_execution(
                    organization_id=organization_id, actor_id=user.id,
                    connection_id=preflight.get("connection_id"),
                    operation_type=f"control_plane.{action}", resource_id=op.id,
                    correlation_id=correlation_id, outcome="failed", result_summary=result,
                )
            else:
                op.result = {**result, "integration_readiness": preflight.get("evidence_context"), "correlation_id": correlation_id}
                op.status = OperationStatus.SUCCEEDED.value
                op.executed_at = datetime.now(UTC)
                await gate.record_execution(
                    organization_id=organization_id, actor_id=user.id,
                    connection_id=preflight.get("connection_id"),
                    operation_type=f"control_plane.{action}", resource_id=op.id,
                    correlation_id=correlation_id, outcome="succeeded", result_summary=result,
                    verification={"verified": result.get("success", True) is not False},
                )
        except Exception as exc:  # noqa: BLE001
            op.status = OperationStatus.FAILED.value
            op.error = str(exc)[:500]
            await gate.record_execution(
                organization_id=organization_id, actor_id=user.id,
                connection_id=preflight.get("connection_id"),
                operation_type=f"control_plane.{action}", resource_id=op.id,
                correlation_id=correlation_id, outcome="failed",
            )
        await self.audit.log(
            action="control_plane_operation_executed", resource_type="cp_operation",
            resource_id=op.id, user_id=user.id, details={"status": op.status},
        )
        return op

    async def list_operations(self, user: User, org_context: OrgContext) -> list[ControlPlaneOperation]:
        self._ensure_read(user, org_context)
        return await self.operations.list_for_org(org_context.requires_organization)

    async def read_cluster(
        self, user: User, org_context: OrgContext, cluster_id: str, action: str, params: dict,
    ) -> dict:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        cluster = await self.clusters.get_for_org(cluster_id, organization_id)
        if not cluster:
            raise NotFoundError("Cluster", cluster_id)
        secret = await self._resolve_secret(cluster.credential_id, user, org_context)
        return await k8s_ops.execute_read(secret, action, params)

    # ------------------------------------------------------------- inventory
    async def unified_inventory(self, user: User, org_context: OrgContext) -> list[dict]:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        items: list[dict] = []
        for row in await self.cloud_inventory.unified_inventory(organization_id):
            items.append({
                "source": "cloud", "provider": row.provider, "cloud": row.account,
                "region": row.region, "cluster": None, "namespace": None,
                "resource_type": row.resource_type, "resource_name": row.resource_name,
                "owner": row.owner, "environment": row.environment, "health": row.health,
                "tags": row.tags or {},
            })
        for cluster in await self.clusters.list_for_org(organization_id):
            for res in await self.cluster_resources.list_for_cluster(organization_id, cluster.id):
                items.append({
                    "source": "cluster", "provider": cluster.distribution,
                    "cloud": None, "region": None, "cluster": cluster.name,
                    "namespace": res.namespace, "resource_type": res.kind,
                    "resource_name": res.name, "owner": (res.labels or {}).get("owner"),
                    "environment": (res.labels or {}).get("env"),
                    "health": res.health, "tags": res.labels or {},
                })
        return items

    async def federation_summary(self, user: User, org_context: OrgContext) -> dict:
        """Cross-cluster inventory aggregate with advisory DR readiness signals."""
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        clusters = await self.clusters.list_for_org(organization_id)
        accounts = await self.cloud_accounts.list_for_org(organization_id)
        inventory = await self.unified_inventory(user, org_context)
        providers = sorted({
            *(a.provider for a in accounts if a.provider),
            *(c.distribution for c in clusters if c.distribution),
        })
        regions = {
            *(getattr(a, "region", None) for a in accounts if getattr(a, "region", None)),
            *(getattr(c, "region", None) for c in clusters if getattr(c, "region", None)),
        }
        healthy = sum(1 for c in clusters if str(c.health or "").upper() in {"HEALTHY", "OK", "CONNECTED"})
        dr_readiness = {
            "multi_cluster": len(clusters) >= 2,
            "multi_region": len(regions) >= 2,
            "healthy_clusters": healthy,
            "cloud_accounts": len(accounts),
            "inventory_items": len(inventory),
            "failover_candidates": healthy if len(clusters) >= 2 else 0,
        }
        dr_mode = "advisory_inventory" if len(clusters) >= 2 else "inventory_aggregate"
        recommended: list[str] = []
        if len(clusters) < 2:
            recommended.append("Register a secondary cluster to enable cross-cluster DR inventory.")
        if len(regions) < 2:
            recommended.append("Add cloud accounts or clusters in a second region for geographic redundancy.")
        if healthy < len(clusters) and clusters:
            recommended.append("Resolve unhealthy cluster connectivity before relying on failover inventory.")
        return {
            "cluster_count": len(clusters),
            "cloud_account_count": len(accounts),
            "inventory_count": len(inventory),
            "providers": providers,
            "federation_mode": "inventory_aggregate",
            "dr_orchestration": dr_mode,
            "dr_readiness": dr_readiness,
            "recommended_actions": recommended,
            "clusters": [
                {
                    "id": c.id,
                    "name": c.name,
                    "distribution": c.distribution,
                    "health": c.health,
                    "node_count": c.node_count,
                    "namespace_count": c.namespace_count,
                }
                for c in clusters
            ],
        }

    # ------------------------------------------------------------- policies
    async def list_policy_findings(
        self, user: User, org_context: OrgContext, cluster_id: str,
    ) -> list[ClusterPolicyFinding]:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        from sqlalchemy import select

        stmt = select(ClusterPolicyFinding).where(
            ClusterPolicyFinding.organization_id == organization_id,
            ClusterPolicyFinding.cluster_id == cluster_id,
        )
        return list((await self.session.execute(stmt)).scalars().all())

    # ------------------------------------------------------------------ helm
    async def list_helm_releases(self, user: User, org_context: OrgContext, cluster_id: str):
        self._ensure_read(user, org_context)
        cluster = await self.clusters.get_for_org(cluster_id, org_context.requires_organization)
        if not cluster:
            raise NotFoundError("Cluster", cluster_id)
        return helm_mod.list_installed_releases(cluster.name)

    # ---------------------------------------------------------------- gitops
    async def list_gitops_apps(self, user: User, org_context: OrgContext, cluster_id: str):
        self._ensure_read(user, org_context)
        cluster = await self.clusters.get_for_org(cluster_id, org_context.requires_organization)
        if not cluster:
            raise NotFoundError("Cluster", cluster_id)
        return gitops_mod.list_gitops_applications(cluster.name)

    # ------------------------------------------------------------------ meta
    @staticmethod
    def supported_providers() -> dict:
        return {"cloud": supported_cloud_providers(), "kubernetes": supported_distributions()}
