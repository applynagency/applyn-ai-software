# Advanced Kubernetes Operations (Sprint 65A)

Transforms the Control Plane into a full Kubernetes operations platform by **extending** existing Sprint 63A infrastructure — no duplicate engines.

## Architecture

`K8sOperationsService` orchestrates:

| Capability | Reused From |
|------------|-------------|
| Cluster access & secrets | `ControlPlaneService`, `SecretManagerService` |
| Approval workflow | `propose → decide → execute` on `cp_operations` |
| K8s API execution | `app/control_plane/kubernetes/operations.py` |
| Diagnostics bundles | `app/control_plane/kubernetes/diagnostics.py` |
| Health scoring | `app/control_plane/kubernetes/health.py` |
| Audit | `AuditLogRepository` |
| Events | Domain event bus |

## API

Base: `/v1/control-plane/clusters/{cluster_id}/k8s`

| Endpoint | Description |
|----------|-------------|
| `GET /capabilities` | Supported read actions and write kinds |
| `GET /overview` | Cluster health score and resource counts |
| `POST /read` | Generic read operation (logs, describe, events, …) |
| `GET /pods`, `/nodes`, `/namespaces` | Resource lists |
| `GET /workloads/{kind}` | Deployments, StatefulSets, Jobs, … |
| `GET /storage/{kind}` | PVC, PV, StorageClasses |
| `GET /networking/{kind}` | Services, Ingress, NetworkPolicies |
| `POST /diagnostics` | Collect full diagnostics bundle |
| `GET /diagnostics` | List saved bundles |
| `POST /operations` | Propose approval-gated mutation |
| `POST /operations/{id}/decide` | Approve/reject |
| `POST /operations/{id}/execute` | Execute approved operation |

All **write** operations require approval.

## Operation Kinds (extended)

Pods: `DELETE_POD`, `RESTART_POD`, `EVICT_POD`  
Workloads: `SCALE_DEPLOYMENT`, `PAUSE_ROLLOUT`, `RESUME_ROLLOUT`, `UPDATE_IMAGE`, `UPDATE_RESOURCES`, `ROLLBACK_DEPLOYMENT`  
Nodes: `CORDON_NODE`, `UNCORDON_NODE`, `DRAIN_NODE`, `MAINTENANCE_NODE`  
Namespaces: `CREATE_NAMESPACE`, `DELETE_NAMESPACE`  
Storage: `EXPAND_PVC`  
Networking: `APPLY_NETWORK_POLICY`

## Events

`PodRestarted`, `DeploymentScaled`, `RolloutStarted`, `RolloutCompleted`, `NodeDrained`, `NamespaceCreated`, `PVCExpanded`, `NetworkPolicyApplied`, `DiagnosticsCollected`

## Prometheus Metrics

- `nexora_k8s_operations_total{mode,action,status}`
- `nexora_k8s_operation_duration_seconds{mode,action}`
- `nexora_k8s_cluster_health_score{cluster_id}`
- `nexora_k8s_resource_counts{cluster_id,kind}`
- `nexora_k8s_pod_restarts_total{cluster_id,status}`

## AI Tools (evidence-grounded)

- `k8s.debug_pod`
- `k8s.find_restart_reason`
- `k8s.explain_events`
- `k8s.recommend_resources`
- `k8s.find_unused_resources`
- `k8s.optimize_namespace`
- `k8s.explain_rollout`

## Database

- `cp_k8s_diagnostics` — stored diagnostics bundles

Migration: `0027_k8s_operations`

## UI

Integrated under Control Plane cluster detail and `/control-plane/k8s` routes.
