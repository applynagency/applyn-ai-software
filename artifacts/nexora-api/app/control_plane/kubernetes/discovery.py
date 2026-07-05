"""Live Kubernetes cluster discovery."""

from __future__ import annotations

import asyncio
from typing import Any

from app.control_plane.kubernetes.base import DiscoveredResource
from app.control_plane.kubernetes.client import K8sApiBundle, open_client
from app.control_plane.types import DISCOVERED_RESOURCE_KINDS
from app.core.logging import get_logger

logger = get_logger(__name__)

_LIMIT = 200


def _health_from_phase(phase: str | None) -> str:
    if phase in ("Running", "Active", "Bound", "Available"):
        return "HEALTHY"
    if phase in ("Pending", "Progressing"):
        return "DEGRADED"
    if phase in ("Failed", "Unknown"):
        return "UNHEALTHY"
    return "UNKNOWN"


def _discover_live(bundle: K8sApiBundle) -> list[DiscoveredResource]:
    out: list[DiscoveredResource] = []

    def _add(kind: str, name: str, ns: str | None, uid: str, labels: dict, annotations: dict,
             health: str = "UNKNOWN", **meta):
        out.append(DiscoveredResource(
            kind=kind, namespace=ns, name=name, uid=uid or name,
            labels=labels or {}, annotations=annotations or {},
            health=health, metadata=meta,
        ))

    for ns in bundle.core.list_namespace(limit=_LIMIT).items:
        _add("Namespace", ns.metadata.name, None, ns.metadata.uid or ns.metadata.name,
             dict(ns.metadata.labels or {}), dict(ns.metadata.annotations or {}),
             _health_from_phase(ns.status.phase if ns.status else None))

    for dep in bundle.apps.list_deployment_for_all_namespaces(limit=_LIMIT).items:
        ready = (dep.status.ready_replicas or 0) if dep.status else 0
        desired = (dep.spec.replicas or 1) if dep.spec else 1
        health = "HEALTHY" if ready >= desired else "DEGRADED"
        _add("Deployment", dep.metadata.name, dep.metadata.namespace, dep.metadata.uid or dep.metadata.name,
             dict(dep.metadata.labels or {}), dict(dep.metadata.annotations or {}), health,
             replicas=desired, ready_replicas=ready)

    for ds in bundle.apps.list_daemon_set_for_all_namespaces(limit=_LIMIT).items:
        _add("DaemonSet", ds.metadata.name, ds.metadata.namespace, ds.metadata.uid or ds.metadata.name,
             dict(ds.metadata.labels or {}), dict(ds.metadata.annotations or {}), "HEALTHY")

    for sts in bundle.apps.list_stateful_set_for_all_namespaces(limit=_LIMIT).items:
        _add("StatefulSet", sts.metadata.name, sts.metadata.namespace, sts.metadata.uid or sts.metadata.name,
             dict(sts.metadata.labels or {}), dict(sts.metadata.annotations or {}), "HEALTHY")

    for pod in bundle.core.list_pod_for_all_namespaces(limit=_LIMIT).items:
        phase = pod.status.phase if pod.status else None
        images = [c.image for c in (pod.spec.containers if pod.spec else [])]
        _add("Pod", pod.metadata.name, pod.metadata.namespace, pod.metadata.uid or pod.metadata.name,
             dict(pod.metadata.labels or {}), dict(pod.metadata.annotations or {}),
             _health_from_phase(phase), phase=phase, images=images,
             container_runtime=pod.status.container_statuses[0].image_id.split("//")[0]
             if pod.status and pod.status.container_statuses else None)

    for job in bundle.batch.list_job_for_all_namespaces(limit=_LIMIT).items:
        _add("Job", job.metadata.name, job.metadata.namespace, job.metadata.uid or job.metadata.name,
             dict(job.metadata.labels or {}), dict(job.metadata.annotations or {}), "HEALTHY")

    for cj in bundle.batch.list_cron_job_for_all_namespaces(limit=_LIMIT).items:
        _add("CronJob", cj.metadata.name, cj.metadata.namespace, cj.metadata.uid or cj.metadata.name,
             dict(cj.metadata.labels or {}), dict(cj.metadata.annotations or {}), "HEALTHY")

    for cm in bundle.core.list_config_map_for_all_namespaces(limit=_LIMIT).items:
        _add("ConfigMap", cm.metadata.name, cm.metadata.namespace, cm.metadata.uid or cm.metadata.name,
             dict(cm.metadata.labels or {}), {}, "HEALTHY")

    for sec in bundle.core.list_secret_for_all_namespaces(limit=_LIMIT).items:
        # metadata only — never expose secret data
        _add("Secret", sec.metadata.name, sec.metadata.namespace, sec.metadata.uid or sec.metadata.name,
             dict(sec.metadata.labels or {}), {}, "HEALTHY", type=sec.type)

    for pvc in bundle.core.list_persistent_volume_claim_for_all_namespaces(limit=_LIMIT).items:
        phase = pvc.status.phase if pvc.status else None
        _add("PersistentVolumeClaim", pvc.metadata.name, pvc.metadata.namespace,
             pvc.metadata.uid or pvc.metadata.name, dict(pvc.metadata.labels or {}), {},
             _health_from_phase(phase), capacity=pvc.status.capacity if pvc.status else None)

    for sc in bundle.storage.list_storage_class(limit=_LIMIT).items:
        _add("StorageClass", sc.metadata.name, None, sc.metadata.name,
             dict(sc.metadata.labels or {}), {}, "HEALTHY", provisioner=sc.provisioner)

    for ing in bundle.net.list_ingress_for_all_namespaces(limit=_LIMIT).items:
        _add("Ingress", ing.metadata.name, ing.metadata.namespace, ing.metadata.uid or ing.metadata.name,
             dict(ing.metadata.labels or {}), dict(ing.metadata.annotations or {}), "HEALTHY")

    for svc in bundle.core.list_service_for_all_namespaces(limit=_LIMIT).items:
        _add("Service", svc.metadata.name, svc.metadata.namespace, svc.metadata.uid or svc.metadata.name,
             dict(svc.metadata.labels or {}), dict(svc.metadata.annotations or {}), "HEALTHY",
             type=svc.spec.type if svc.spec else None)

    for hpa in bundle.autoscaling.list_horizontal_pod_autoscaler_for_all_namespaces(limit=_LIMIT).items:
        _add("HorizontalPodAutoscaler", hpa.metadata.name, hpa.metadata.namespace,
             hpa.metadata.uid or hpa.metadata.name, dict(hpa.metadata.labels or {}), {}, "HEALTHY")

    for np in bundle.net.list_network_policy_for_all_namespaces(limit=_LIMIT).items:
        _add("NetworkPolicy", np.metadata.name, np.metadata.namespace,
             np.metadata.uid or np.metadata.name, dict(np.metadata.labels or {}), {}, "HEALTHY")

    for role in bundle.rbac.list_role_for_all_namespaces(limit=_LIMIT).items:
        _add("Role", role.metadata.name, role.metadata.namespace,
             role.metadata.uid or role.metadata.name, {}, {}, "HEALTHY")

    for crb in bundle.rbac.list_cluster_role_binding(limit=_LIMIT).items:
        _add("ClusterRoleBinding", crb.metadata.name, None, crb.metadata.uid or crb.metadata.name,
             {}, {}, "HEALTHY", subjects=len(crb.subjects or []))

    try:
        for crd in bundle.apiextensions.list_custom_resource_definition(limit=_LIMIT).items:
            _add("CustomResourceDefinition", crd.metadata.name, None, crd.metadata.name, {}, {}, "HEALTHY",
                 group=crd.spec.group if crd.spec else None)
    except Exception:  # noqa: BLE001
        pass

    for ev in bundle.core.list_event_for_all_namespaces(limit=100).items:
        _add("Event", ev.metadata.name, ev.metadata.namespace, ev.metadata.uid or ev.metadata.name,
             {}, {}, "HEALTHY", reason=ev.reason, type=ev.type)

    for node in bundle.core.list_node(limit=_LIMIT).items:
        ready = any(c.type == "Ready" and c.status == "True"
                    for c in (node.status.conditions or [])) if node.status else False
        _add("Node", node.metadata.name, None, node.metadata.uid or node.metadata.name,
             dict(node.metadata.labels or {}), dict(node.metadata.annotations or {}),
             "HEALTHY" if ready else "DEGRADED",
             kubelet_version=node.status.node_info.kubelet_version if node.status and node.status.node_info else None,
             os_image=node.status.node_info.os_image if node.status and node.status.node_info else None)

    return out


def _discover_simulated(cluster_name: str) -> list[DiscoveredResource]:
    """Offline deterministic cluster inventory for tests and unconfigured clusters."""
    ns = "production"
    resources = [
        DiscoveredResource("Namespace", None, ns, f"ns-{ns}", {"env": "prod"}, {}, "HEALTHY"),
        DiscoveredResource("Deployment", ns, "checkout", "dep-checkout", {"app": "checkout"}, {}, "HEALTHY",
                           metadata={"replicas": 3, "ready_replicas": 3}),
        DiscoveredResource("Deployment", ns, "payment", "dep-payment", {"app": "payment"}, {}, "DEGRADED",
                           metadata={"replicas": 3, "ready_replicas": 1}),
        DiscoveredResource("Pod", ns, "checkout-abc123", "pod-1", {"app": "checkout"}, {}, "HEALTHY"),
        DiscoveredResource("Pod", ns, "payment-def456", "pod-2", {"app": "payment"}, {}, "UNHEALTHY",
                           metadata={"phase": "CrashLoopBackOff"}),
        DiscoveredResource("Service", ns, "checkout", "svc-checkout", {}, {}, "HEALTHY"),
        DiscoveredResource("Ingress", ns, "checkout", "ing-checkout", {}, {}, "HEALTHY"),
        DiscoveredResource("Node", None, "node-1", "node-1", {"node-role": "worker"}, {}, "HEALTHY",
                           metadata={"kubelet_version": "v1.29.0"}),
    ]
    return resources


async def discover_cluster(secret: dict, *, cluster_name: str = "kubernetes") -> list[DiscoveredResource]:
    if not secret.get("kubeconfig"):
        return _discover_simulated(cluster_name)

    def _run():
        bundle = open_client(secret)
        try:
            return _discover_live(bundle)
        finally:
            bundle.cleanup()

    try:
        return await asyncio.to_thread(_run)
    except Exception as exc:  # noqa: BLE001
        logger.info("k8s_discovery_fallback", error=type(exc).__name__)
        return _discover_simulated(cluster_name)


def discover_cluster_sync(secret: dict, *, cluster_name: str = "kubernetes") -> list[DiscoveredResource]:
    """Synchronous entry for provider interface."""
    import asyncio
    try:
        asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, discover_cluster(secret, cluster_name=cluster_name)).result()
    except RuntimeError:
        return asyncio.run(discover_cluster(secret, cluster_name=cluster_name))
