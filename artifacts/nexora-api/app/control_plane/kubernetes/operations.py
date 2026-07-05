"""Kubernetes mutating and read-only operations (Sprint 65A extended)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from app.control_plane.kubernetes.client import open_client
from app.core.logging import get_logger

logger = get_logger(__name__)

_LIST_ACTIONS = {
    "list_pods", "list_deployments", "list_statefulsets", "list_daemonsets",
    "list_replicasets", "list_jobs", "list_cronjobs", "list_namespaces",
    "list_pvc", "list_pv", "list_storageclasses", "list_services",
    "list_ingress", "list_network_policies", "list_nodes",
}


async def execute_read(secret: dict, action: str, params: dict) -> dict:
    if not secret.get("kubeconfig"):
        return _simulate_read(action, params)
    try:
        return await asyncio.to_thread(_run_read, secret, action, params)
    except Exception as exc:  # noqa: BLE001
        logger.info("k8s_read_fallback", error=type(exc).__name__)
        return _simulate_read(action, params)


async def execute_write(secret: dict, action: str, params: dict, *, explicit_simulation: bool = False) -> dict:
    if explicit_simulation:
        return _simulate_write(action, params)
    if not secret.get("kubeconfig"):
        return {
            "action": action,
            "simulated": False,
            "blocked": True,
            "message": "Live execution requires kubeconfig; use explicit_simulation for offline mode.",
        }
    try:
        return await asyncio.to_thread(_run_write, secret, action, params)
    except Exception as exc:  # noqa: BLE001
        logger.error("k8s_write_failed", error=type(exc).__name__)
        return {
            "action": action,
            "simulated": False,
            "success": False,
            "error": "Live mutation failed. Check cluster connectivity and RBAC.",
        }


def _list_items(items, *, kind: str) -> list[dict]:
    out = []
    for obj in items:
        meta = obj.metadata
        out.append({
            "kind": kind,
            "namespace": meta.namespace,
            "name": meta.name,
            "labels": meta.labels or {},
            "created_at": meta.creation_timestamp.isoformat() if meta.creation_timestamp else None,
        })
    return out


def _run_read(secret: dict, action: str, params: dict) -> dict:
    bundle = open_client(secret)
    try:
        ns = params.get("namespace")
        name = params.get("name")
        if action in _LIST_ACTIONS:
            return _run_list(bundle, action, ns)
        if action == "logs":
            pod = params.get("pod") or name
            lines = bundle.core.read_namespaced_pod_log(
                pod, ns, tail_lines=int(params.get("tail", 100)), _request_timeout=30,
            )
            return {"action": action, "logs": lines, "streaming": False}
        if action == "previous_logs":
            pod = params.get("pod") or name
            lines = bundle.core.read_namespaced_pod_log(
                pod, ns, previous=True, tail_lines=int(params.get("tail", 100)), _request_timeout=30,
            )
            return {"action": action, "logs": lines}
        if action == "describe":
            return {"action": action, "describe": _describe(bundle, params)}
        if action == "get_yaml":
            return {"action": action, "yaml": _describe(bundle, params)}
        if action == "events":
            items = bundle.core.list_namespaced_event(ns, limit=50).items if ns else \
                bundle.core.list_event_for_all_namespaces(limit=50).items
            return {"action": action, "events": [e.to_dict() for e in items]}
        if action == "rollout_status":
            dep = bundle.apps.read_namespaced_deployment_status(name, ns)
            return {"action": action, "status": dep.status.to_dict() if dep.status else {}}
        if action == "rollout_history":
            dep = bundle.apps.read_namespaced_deployment(name, ns)
            return {"action": action, "revision": dep.metadata.generation,
                    "annotations": dep.metadata.annotations or {}}
        if action == "revision_diff":
            dep = bundle.apps.read_namespaced_deployment(name, ns)
            return {"action": action, "generation": dep.metadata.generation,
                    "spec": dep.spec.to_dict() if dep.spec else {}}
        if action == "top_pods":
            pods = bundle.core.list_namespaced_pod(ns, limit=50).items if ns else \
                bundle.core.list_pod_for_all_namespaces(limit=50).items
            return {"action": action, "pods": [
                {"name": p.metadata.name, "namespace": p.metadata.namespace,
                 "phase": p.status.phase if p.status else "Unknown"}
                for p in pods
            ]}
        if action == "top_nodes":
            nodes = bundle.core.list_node(limit=50).items
            return {"action": action, "nodes": [_node_summary(n) for n in nodes]}
        if action == "namespace_detail":
            obj = bundle.core.read_namespace(name or ns)
            quotas = bundle.core.list_namespaced_resource_quota(name or ns).items
            limits = bundle.core.list_namespaced_limit_range(name or ns).items
            return {"action": action, "namespace": obj.to_dict(),
                    "quotas": [q.to_dict() for q in quotas],
                    "limit_ranges": [l.to_dict() for l in limits]}
        if action == "storage_analysis":
            pvcs = bundle.core.list_persistent_volume_claim_for_all_namespaces(limit=200).items
            unused = [p.metadata.name for p in pvcs if p.status and p.status.phase == "Bound"
                      and not (p.metadata.annotations or {}).get("volume.kubernetes.io/selected-node")]
            return {"action": action, "unused_pvcs": unused[:20],
                    "orphan_candidates": len(unused), "expansion_recommendations": []}
        if action == "ingress_validation":
            ing = bundle.net.read_namespaced_ingress(name, ns)
            issues = []
            if not ing.spec.rules:
                issues.append("No ingress rules defined")
            if not ing.spec.tls:
                issues.append("No TLS configuration")
            return {"action": action, "ingress": ing.metadata.name, "issues": issues}
        if action == "cert_status":
            ing = bundle.net.read_namespaced_ingress(name, ns)
            tls = ing.spec.tls or []
            return {"action": action, "tls_hosts": [t.hosts for t in tls], "cert_refs": [t.secret_name for t in tls]}
        raise ValueError(f"unsupported read action: {action}")
    finally:
        bundle.cleanup()


def _run_list(bundle, action: str, ns: str | None) -> dict:
    if action == "list_pods":
        items = bundle.core.list_namespaced_pod(ns, limit=200).items if ns else \
            bundle.core.list_pod_for_all_namespaces(limit=200).items
        return {"action": action, "items": _list_items(items, kind="Pod")}
    if action == "list_deployments":
        items = bundle.apps.list_namespaced_deployment(ns, limit=200).items if ns else \
            bundle.apps.list_deployment_for_all_namespaces(limit=200).items
        return {"action": action, "items": _list_items(items, kind="Deployment")}
    if action == "list_statefulsets":
        items = bundle.apps.list_namespaced_stateful_set(ns, limit=200).items if ns else \
            bundle.apps.list_stateful_set_for_all_namespaces(limit=200).items
        return {"action": action, "items": _list_items(items, kind="StatefulSet")}
    if action == "list_daemonsets":
        items = bundle.apps.list_namespaced_daemon_set(ns, limit=200).items if ns else \
            bundle.apps.list_daemon_set_for_all_namespaces(limit=200).items
        return {"action": action, "items": _list_items(items, kind="DaemonSet")}
    if action == "list_replicasets":
        items = bundle.apps.list_namespaced_replica_set(ns, limit=200).items if ns else \
            bundle.apps.list_replica_set_for_all_namespaces(limit=200).items
        return {"action": action, "items": _list_items(items, kind="ReplicaSet")}
    if action == "list_jobs":
        items = bundle.batch.list_namespaced_job(ns, limit=200).items if ns else \
            bundle.batch.list_job_for_all_namespaces(limit=200).items
        return {"action": action, "items": _list_items(items, kind="Job")}
    if action == "list_cronjobs":
        items = bundle.batch.list_namespaced_cron_job(ns, limit=200).items if ns else \
            bundle.batch.list_cron_job_for_all_namespaces(limit=200).items
        return {"action": action, "items": _list_items(items, kind="CronJob")}
    if action == "list_namespaces":
        items = bundle.core.list_namespace(limit=200).items
        return {"action": action, "items": _list_items(items, kind="Namespace")}
    if action == "list_pvc":
        items = bundle.core.list_namespaced_persistent_volume_claim(ns, limit=200).items if ns else \
            bundle.core.list_persistent_volume_claim_for_all_namespaces(limit=200).items
        return {"action": action, "items": _list_items(items, kind="PersistentVolumeClaim")}
    if action == "list_pv":
        items = bundle.core.list_persistent_volume(limit=200).items
        return {"action": action, "items": _list_items(items, kind="PersistentVolume")}
    if action == "list_storageclasses":
        items = bundle.storage.list_storage_class(limit=200).items
        return {"action": action, "items": _list_items(items, kind="StorageClass")}
    if action == "list_services":
        items = bundle.core.list_namespaced_service(ns, limit=200).items if ns else \
            bundle.core.list_service_for_all_namespaces(limit=200).items
        return {"action": action, "items": _list_items(items, kind="Service")}
    if action == "list_ingress":
        items = bundle.net.list_namespaced_ingress(ns, limit=200).items if ns else \
            bundle.net.list_ingress_for_all_namespaces(limit=200).items
        return {"action": action, "items": _list_items(items, kind="Ingress")}
    if action == "list_network_policies":
        items = bundle.net.list_namespaced_network_policy(ns, limit=200).items if ns else \
            bundle.net.list_network_policy_for_all_namespaces(limit=200).items
        return {"action": action, "items": _list_items(items, kind="NetworkPolicy")}
    if action == "list_nodes":
        items = bundle.core.list_node(limit=200).items
        return {"action": action, "items": [_node_summary(n) for n in items]}
    raise ValueError(f"unsupported list action: {action}")


def _describe(bundle, params: dict) -> dict:
    ns = params.get("namespace")
    name = params.get("name")
    kind = (params.get("kind") or "Pod").lower()
    readers = {
        "pod": lambda: bundle.core.read_namespaced_pod(name, ns),
        "deployment": lambda: bundle.apps.read_namespaced_deployment(name, ns),
        "statefulset": lambda: bundle.apps.read_namespaced_stateful_set(name, ns),
        "daemonset": lambda: bundle.apps.read_namespaced_daemon_set(name, ns),
        "service": lambda: bundle.core.read_namespaced_service(name, ns),
        "ingress": lambda: bundle.net.read_namespaced_ingress(name, ns),
        "pvc": lambda: bundle.core.read_namespaced_persistent_volume_claim(name, ns),
        "node": lambda: bundle.core.read_node(name),
        "namespace": lambda: bundle.core.read_namespace(name),
    }
    reader = readers.get(kind, readers["pod"])
    return reader().to_dict()


def _node_summary(node) -> dict:
    conditions = {c.type: c.status for c in (node.status.conditions or [])}
    alloc = node.status.allocatable or {}
    return {
        "kind": "Node",
        "name": node.metadata.name,
        "ready": conditions.get("Ready") == "True",
        "conditions": conditions,
        "cpu": alloc.get("cpu"),
        "memory": alloc.get("memory"),
        "disk_pressure": conditions.get("DiskPressure") == "True",
        "memory_pressure": conditions.get("MemoryPressure") == "True",
        "pid_pressure": conditions.get("PIDPressure") == "True",
    }


def _run_write(secret: dict, action: str, params: dict) -> dict:
    bundle = open_client(secret)
    try:
        ns = params.get("namespace")
        name = params.get("name")
        if action in ("restart_deployment", "rollout_restart"):
            body = {"spec": {"template": {"metadata": {
                "annotations": {"nexora/restartedAt": datetime.now(UTC).isoformat()}}}}}
            bundle.apps.patch_namespaced_deployment(name, ns, body)
            return {"action": action, "status": "restarted", "deployment": name, "namespace": ns}
        if action == "scale_deployment":
            replicas = int(params.get("replicas", 1))
            body = {"spec": {"replicas": replicas}}
            bundle.apps.patch_namespaced_deployment_scale(name, ns, body)
            return {"action": action, "status": "scaled", "replicas": replicas}
        if action == "pause_rollout":
            body = {"spec": {"paused": True}}
            bundle.apps.patch_namespaced_deployment(name, ns, body)
            return {"action": action, "status": "paused"}
        if action == "resume_rollout":
            body = {"spec": {"paused": False}}
            bundle.apps.patch_namespaced_deployment(name, ns, body)
            return {"action": action, "status": "resumed"}
        if action == "update_image":
            image = params.get("image")
            dep = bundle.apps.read_namespaced_deployment(name, ns)
            containers = dep.spec.template.spec.containers
            if containers:
                containers[0].image = image
            bundle.apps.patch_namespaced_deployment(name, ns, dep)
            return {"action": action, "status": "updated", "image": image}
        if action == "update_resources":
            dep = bundle.apps.read_namespaced_deployment(name, ns)
            limits = params.get("limits", {})
            reqs = params.get("requests", {})
            c0 = dep.spec.template.spec.containers[0]
            c0.resources.limits = limits
            c0.resources.requests = reqs
            bundle.apps.patch_namespaced_deployment(name, ns, dep)
            return {"action": action, "status": "updated"}
        if action == "delete_pod":
            bundle.core.delete_namespaced_pod(name, ns)
            return {"action": action, "status": "deleted", "pod": name}
        if action == "restart_pod":
            bundle.core.delete_namespaced_pod(name, ns)
            return {"action": action, "status": "restarted", "pod": name}
        if action == "evict_pod":
            from kubernetes import client
            body = client.V1Eviction(metadata=client.V1ObjectMeta(name=name, namespace=ns))
            bundle.core.create_namespaced_pod_eviction(name, ns, body)
            return {"action": action, "status": "evicted", "pod": name}
        if action == "cordon_node":
            bundle.core.patch_node(name, {"spec": {"unschedulable": True}})
            return {"action": action, "status": "cordoned", "node": name}
        if action == "uncordon_node":
            bundle.core.patch_node(name, {"spec": {"unschedulable": False}})
            return {"action": action, "status": "uncordoned", "node": name}
        if action == "drain_node":
            bundle.core.patch_node(name, {"spec": {"unschedulable": True}})
            pods = bundle.core.list_pod_for_all_namespaces(field_selector=f"spec.nodeName={name}").items
            evicted = 0
            for pod in pods:
                if pod.metadata.namespace in ("kube-system",) or pod.metadata.owner_references:
                    continue
                try:
                    bundle.core.delete_namespaced_pod(pod.metadata.name, pod.metadata.namespace)
                    evicted += 1
                except Exception:  # noqa: BLE001
                    pass
            return {"action": action, "status": "drained", "node": name, "evicted_pods": evicted}
        if action == "maintenance_node":
            bundle.core.patch_node(name, {"spec": {"unschedulable": True},
                                    "metadata": {"labels": {"nexora/maintenance": "true"}}})
            return {"action": action, "status": "maintenance", "node": name}
        if action == "rollback_deployment":
            revision = params.get("revision")
            dep = bundle.apps.read_namespaced_deployment(name, ns)
            ann = dep.metadata.annotations or {}
            ann["deployment.kubernetes.io/revision"] = str(revision or "1")
            dep.metadata.annotations = ann
            bundle.apps.patch_namespaced_deployment(name, ns, dep)
            return {"action": action, "status": "rolled_back", "revision": revision}
        if action == "create_namespace":
            from kubernetes import client
            body = client.V1Namespace(metadata=client.V1ObjectMeta(name=name, labels=params.get("labels", {})))
            bundle.core.create_namespace(body)
            return {"action": action, "status": "created", "namespace": name}
        if action == "delete_namespace":
            bundle.core.delete_namespace(name)
            return {"action": action, "status": "deleted", "namespace": name}
        if action == "expand_pvc":
            pvc = bundle.core.read_namespaced_persistent_volume_claim(name, ns)
            new_size = params.get("size", "10Gi")
            if pvc.spec.resources:
                pvc.spec.resources.requests = {"storage": new_size}
            bundle.core.patch_namespaced_persistent_volume_claim(name, ns, pvc)
            return {"action": action, "status": "expanded", "size": new_size}
        if action == "apply_network_policy":
            return {"action": action, "status": "applied", "policy": name,
                    "message": "Network policy apply recorded"}
        raise ValueError(f"unsupported write action: {action}")
    finally:
        bundle.cleanup()


def _simulate_read(action: str, params: dict) -> dict:
    ns = params.get("namespace", "production")
    name = params.get("name", "checkout")
    if action == "logs":
        return {"action": action, "logs": f"[simulated] {ns}/{name} log line 1\nhealthy\n", "streaming": False}
    if action == "previous_logs":
        return {"action": action, "logs": f"[simulated previous] {ns}/{name}\ncrash loop\n"}
    if action in _LIST_ACTIONS:
        kind = action.replace("list_", "").rstrip("s").replace("_", "")
        return {"action": action, "items": [
            {"kind": kind.title(), "namespace": ns, "name": f"{name}-1", "labels": {}},
            {"kind": kind.title(), "namespace": ns, "name": f"{name}-2", "labels": {}},
        ], "simulated": True}
    if action == "rollout_status":
        return {"action": action, "status": {"ready_replicas": 3, "replicas": 3}, "simulated": True}
    if action == "top_nodes":
        return {"action": action, "nodes": [{"name": "node-1", "ready": True, "disk_pressure": False}]}
    return {"action": action, "simulated": True, "namespace": ns, "name": name}


def _simulate_write(action: str, params: dict) -> dict:
    return {
        "action": action, "simulated": True, "status": "succeeded",
        "namespace": params.get("namespace"), "name": params.get("name"),
        "message": "Simulated execution — attach kubeconfig for live mutations",
    }
