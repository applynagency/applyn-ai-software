# Nexora — Kubernetes deployment (Sprint 61B)

Production-grade, horizontally scalable, multi-instance deployment. Every node
type coordinates through Redis so there is **no duplicate execution** and **no
process-local runtime state** in production.

## Topology

| Workload | Manifest | Replicas | Role |
|---|---|---|---|
| API | `api-deployment.yaml` | 3–20 (HPA) | Serves HTTP; enqueues jobs |
| Worker (default) | `worker-deployment.yaml` | 2–10 (HPA) | Drains `nexora:jobs` on-demand jobs |
| Worker (high) | `worker-deployment.yaml` | 1 | Drains `nexora:jobs:high` first |
| Scheduler | `scheduler-deployment.yaml` | 1 | Owns cron (discovery/monitoring/escalation/workflow) |

Shared backing services (`db`, `redis`, OTel collector) are environment-provided.

## Apply

```bash
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
# Create the real secret out-of-band; secret.example.yaml is a template only.
kubectl apply -f secret.example.yaml
kubectl apply -f api-deployment.yaml
kubectl apply -f worker-deployment.yaml
kubectl apply -f scheduler-deployment.yaml
```

## HA features wired in

- **HPA** — CPU/memory autoscaling on API and worker.
- **PodDisruptionBudget** — keeps `minAvailable` pods during node drains/upgrades.
- **Pod anti-affinity** — spreads replicas across nodes (`kubernetes.io/hostname`).
- **Rolling updates** — API uses `maxUnavailable: 0` for zero-downtime.
- **Probes** — `/startupz` (slow-boot headroom), `/livez` (process-only, won't
  flap on DB/Redis blips), `/readyz` (gates traffic on dependencies).
- **Graceful termination** — `terminationGracePeriodSeconds` + a `preStop` sleep
  so endpoints leave Service rotation before SIGTERM; workers get 120s to drain.
- **CORS** — set `CORS_ALLOWED_ORIGINS` in the ConfigMap to your browser
  origins (comma-separated). Production with an empty list disables cross-origin
  access; never use `*` with credentials.
- **Exactly-once scheduling** — single scheduler replica + `cron(unique=True)` +
  Redis scheduler lock (triple guard, safe even during rollout overlap).

## Scaling

```bash
kubectl -n nexora scale deploy/nexora-api --replicas=6
kubectl -n nexora scale deploy/nexora-worker --replicas=5
# Scheduler stays at 1 (cron ownership). Do not scale it up.
```
