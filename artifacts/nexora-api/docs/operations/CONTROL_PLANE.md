# Multi-Cloud & Kubernetes Control Plane (Sprint 63A)

Nexora's control plane is the operational layer for cloud accounts and Kubernetes
clusters. It is organization-scoped, provider-abstracted, and integrated with
credentials, audit, events, and the AI tool runtime.

Package: `app/control_plane/`. Service: `app/services/control_plane.py`.
API prefix: `/v1/control-plane`.

## Architecture

```
Credentials (encrypted)
        │
        ▼
CloudProvider / ClusterProvider  ← plugin registry (no duplicated logic)
        │
        ├─ Cloud sync → inventory + cost snapshots
        ├─ Cluster discover → resources + policy findings
        ├─ Read ops (logs, describe, events) — no approval
        └─ Write ops → PENDING_APPROVAL → APPROVED → EXECUTING → SUCCEEDED
```

### Cloud providers

| Provider | Implementation |
|----------|----------------|
| AWS, Azure | Reuses `discovery_adapters` via `_AdapterBackedProvider` |
| GCP, DigitalOcean, Oracle, VMware | `CloudProvider` implementations in `cloud/providers.py` |

### Kubernetes distributions

AKS, EKS, GKE, K3s, RKE2, OpenShift, Vanilla — all use `ClusterProvider` with
shared discovery (`kubernetes/discovery.py`) and operations (`kubernetes/operations.py`).

When a kubeconfig credential is present, discovery uses the Kubernetes Python SDK.
Otherwise a deterministic simulated cluster is used for development and tests.

## REST API

| Endpoint | Description |
|----------|-------------|
| `GET /providers` | Supported cloud and Kubernetes providers |
| `GET/POST /cloud-accounts` | Register and list cloud accounts |
| `POST /cloud-accounts/{id}/sync` | Sync resource inventory |
| `GET /cloud-accounts/{id}/costs` | Cost estimate snapshot |
| `GET/POST /clusters` | Register and list clusters |
| `GET /clusters/{id}` | Cluster detail |
| `POST /clusters/{id}/discover` | Live cluster discovery |
| `GET /clusters/{id}/resources` | Discovered resources (filter by kind/namespace) |
| `GET /clusters/{id}/policies` | Warn-only policy findings |
| `GET /clusters/{id}/helm` | Installed Helm releases (read-only) |
| `GET /clusters/{id}/gitops` | ArgoCD / FluxCD apps (read-only) |
| `POST /clusters/{id}/read` | Read-only ops: logs, describe, events, top |
| `GET/POST /operations` | List / propose cluster mutations |
| `POST /operations/{id}/decide` | Approve or reject |
| `POST /operations/{id}/execute` | Execute approved operation |
| `GET /inventory` | Unified cloud + cluster inventory |

Destructive operations (`SCALE_DEPLOYMENT`, `RESTART_DEPLOYMENT`, `DELETE_POD`,
node cordon/drain, etc.) always start in `PENDING_APPROVAL`.

## Policy scanner

`kubernetes/policies.py` scans discovered resources and records warn-only findings:

- Privileged containers
- `:latest` image tags
- Missing resource limits / probes
- Host networking / PID / IPC
- Cluster-admin bindings
- Public LoadBalancer services
- Deprecated API versions

Findings are never auto-remediated.

## AI integration

Tools registered in `app/ai/tools/control_plane.py`:

| Tool | Kind | Example prompt |
|------|------|----------------|
| `control_plane.list_clusters` | read | "What clusters do we have?" |
| `control_plane.discover_cluster` | write | "Refresh discovery on prod-cluster" |
| `k8s.list_unhealthy_pods` | read | "Show unhealthy pods" |
| `k8s.scale_deployment` | approval | "Scale payment service to 10 replicas" |
| `k8s.restart_deployment` | approval | "Restart checkout deployment" |

Approval tools return `approval_required` until explicitly approved via the
agent runtime or the Operations UI.

## UI

Routes under `/control-plane`:

- Overview — `/control-plane`
- Cloud Accounts — `/control-plane/cloud`
- Clusters — `/control-plane/clusters`
- Cluster detail — `/control-plane/clusters/{id}`
- Inventory — `/control-plane/inventory`
- Operations — `/control-plane/operations`

## Configuration

- `CONTROL_PLANE_ENABLED=true` (default) — mounts the API router
- Requires organization context on all mutating endpoints
- Credentials stored via existing `SecretManagerService` (AES-256-GCM)

## Database

Migration `0022_control_plane` creates:

- `cp_cloud_accounts`, `cp_cloud_sync_runs`, `cp_cloud_inventory`
- `cp_kubernetes_clusters`, `cp_cluster_discovery_runs`, `cp_cluster_resources`
- `cp_operations`, `cp_policy_findings`, `cp_cost_snapshots`

Run `alembic upgrade head` before use.
