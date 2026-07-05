"""Safe pilot operation catalog (Sprint 66B)."""

from __future__ import annotations

PILOT_OPERATION_CATALOG: dict[str, dict] = {
    "k8s_diagnostics": {
        "id": "k8s_diagnostics",
        "name": "Kubernetes diagnostics collection",
        "action": "k8s_diagnostics",
        "mutation": False,
        "reversible": True,
        "required_capabilities": ["kubernetes.read"],
        "description": "Collect read-only cluster/workload diagnostics.",
    },
    "restart_deployment": {
        "id": "restart_deployment",
        "name": "Restart non-production deployment",
        "action": "restart_deployment",
        "mutation": True,
        "reversible": True,
        "required_capabilities": ["kubernetes.workloads.write"],
        "description": "Rolling restart of a selected non-production deployment.",
    },
    "scale_deployment": {
        "id": "scale_deployment",
        "name": "Scale non-production deployment",
        "action": "scale_deployment",
        "mutation": True,
        "reversible": True,
        "required_capabilities": ["kubernetes.workloads.write"],
        "description": "Scale replicas for a selected non-production deployment.",
    },
    "read_deployment_logs": {
        "id": "read_deployment_logs",
        "name": "Read deployment logs/events",
        "action": "read_deployment_logs",
        "mutation": False,
        "reversible": True,
        "required_capabilities": ["kubernetes.read"],
        "description": "Fetch recent events and log excerpts for a deployment.",
    },
    "github_pipeline_sync": {
        "id": "github_pipeline_sync",
        "name": "Read-only GitHub pipeline sync",
        "action": "github_pipeline_sync",
        "mutation": False,
        "reversible": True,
        "required_capabilities": ["source.repositories.read"],
        "description": "Sync repository and pipeline status without mutation.",
    },
    "prometheus_health_query": {
        "id": "prometheus_health_query",
        "name": "Read-only Prometheus health/SLO query",
        "action": "prometheus_health_query",
        "mutation": False,
        "reversible": True,
        "required_capabilities": ["observability.metrics.query"],
        "description": "Query health/SLO metrics from Prometheus.",
    },
}

PILOT_CATALOG_ACTIONS = frozenset(t["action"] for t in PILOT_OPERATION_CATALOG.values())
PILOT_MUTATION_ACTIONS = frozenset(
    t["action"] for t in PILOT_OPERATION_CATALOG.values() if t["mutation"]
)
