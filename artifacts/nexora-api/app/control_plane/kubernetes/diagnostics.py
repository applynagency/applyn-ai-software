"""Kubernetes diagnostics bundle collector (Sprint 65A)."""

from __future__ import annotations

from app.control_plane.kubernetes import operations as k8s_ops


async def collect_diagnostics_bundle(
    secret: dict,
    *,
    namespace: str,
    name: str,
    kind: str = "Pod",
    cluster_resources: list | None = None,
    recent_operations: list | None = None,
) -> dict:
    """Package events, logs, describe, related resources into one bundle."""
    params = {"namespace": namespace, "name": name, "kind": kind, "pod": name}
    events = await k8s_ops.execute_read(secret, "events", {"namespace": namespace})
    logs = await k8s_ops.execute_read(secret, "logs", {**params, "tail": 200})
    prev_logs = await k8s_ops.execute_read(secret, "previous_logs", params)
    describe = await k8s_ops.execute_read(secret, "describe", params)
    yaml_doc = await k8s_ops.execute_read(secret, "get_yaml", params)

    related = _related_resources(cluster_resources or [], namespace=namespace, name=name, kind=kind)
    graph = _resource_graph(related, namespace, name, kind)

    return {
        "target": {"kind": kind, "namespace": namespace, "name": name},
        "events": events.get("events", events),
        "logs": logs.get("logs", ""),
        "previous_logs": prev_logs.get("logs", ""),
        "describe": describe.get("describe", describe),
        "yaml": yaml_doc.get("yaml"),
        "metrics": {"note": "Metrics via discovery metadata; attach Prometheus for live series"},
        "resource_graph": graph,
        "related": related,
        "recent_changes": recent_operations or [],
    }


def _related_resources(resources: list, *, namespace: str, name: str, kind: str) -> dict:
    """Map discovered inventory to related deployments, services, PVCs, etc."""
    ns_resources = [r for r in resources if (r.get("namespace") or "") == namespace]
    out: dict[str, list] = {
        "deployments": [], "configmaps": [], "secrets": [], "pvcs": [],
        "services": [], "ingresses": [],
    }
    kind_map = {
        "Deployment": "deployments", "ConfigMap": "configmaps", "Secret": "secrets",
        "PersistentVolumeClaim": "pvcs", "Service": "services", "Ingress": "ingresses",
    }
    for res in ns_resources:
        bucket = kind_map.get(res.get("kind", ""))
        if bucket:
            out[bucket].append({"name": res.get("name"), "health": res.get("health")})
    if kind == "Pod":
        for dep in out["deployments"]:
            if name.startswith(dep["name"][: max(1, len(dep["name"]) - 1)]):
                out["owner_deployment"] = dep["name"]
    return out


def _resource_graph(related: dict, namespace: str, name: str, kind: str) -> dict:
    nodes = [{"id": f"{kind}/{namespace}/{name}", "kind": kind, "name": name}]
    edges = []
    for svc in related.get("services", []):
        sid = f"Service/{namespace}/{svc['name']}"
        nodes.append({"id": sid, "kind": "Service", "name": svc["name"]})
        edges.append({"from": f"{kind}/{namespace}/{name}", "to": sid, "relation": "exposes"})
    for pvc in related.get("pvcs", []):
        pid = f"PVC/{namespace}/{pvc['name']}"
        nodes.append({"id": pid, "kind": "PersistentVolumeClaim", "name": pvc["name"]})
        edges.append({"from": f"{kind}/{namespace}/{name}", "to": pid, "relation": "mounts"})
    return {"nodes": nodes, "edges": edges}
