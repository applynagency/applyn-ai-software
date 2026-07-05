# DevOps Delivery Platform (Sprint 63B)

Nexora's delivery platform covers the full software delivery lifecycle: source
control, CI/CD pipelines, artifact registries, deployments, releases, GitOps,
security gates, and DORA metrics — all organization-scoped and approval-gated
where required.

Package: `app/delivery/`. Service: `app/services/delivery.py`.
API prefix: `/v1/delivery`.

## Architecture

```
Credentials (GitHub, registry tokens)
        │
        ▼
SourceProvider / PipelineProvider / ArtifactRegistryProvider
        │
        ├─ Repository sync → pipelines → pipeline runs
        ├─ Artifact sync → security scans
        ├─ Releases → approval-gated deployments
        └─ GitOps sync (ArgoCD / Flux)
```

Integrates with Control Plane (`/v1/control-plane`) for cluster operations and
the existing `DeploymentRun` agent pipeline without duplicating deployment engines.

## REST API

| Endpoint | Description |
|----------|-------------|
| `GET /providers` | Supported source, pipeline, artifact, scanner providers |
| `GET /dashboard` | Unified DevOps dashboard + DORA |
| `GET /dora` | DORA four-key metrics |
| `GET/POST /source-connections` | Connect & list source providers |
| `POST /source-connections/{id}/sync` | Sync repositories |
| `GET /repositories` | Repository catalog |
| `GET /repositories/{id}` | Branches, commits, pull requests |
| `GET /pipelines` | Pipeline list |
| `POST /repositories/{id}/pipelines/sync` | Sync pipelines for repo |
| `GET /pipeline-runs` | Recent pipeline runs |
| `POST /pipelines/{id}/runs/sync` | Sync runs for pipeline |
| `POST /artifacts/sync` | Sync artifact registry |
| `GET /artifacts` | Artifact inventory |
| `GET /environments` | Dev/QA/UAT/Staging/Production |
| `GET/POST /releases` | Release management |
| `POST /releases/{id}/approve` | Approve release |
| `GET /deployments` | Deployment history |
| `GET/POST /operations` | Approval-gated deploy/promote/rollback |
| `POST /operations/{id}/decide` | Approve or reject |
| `POST /operations/{id}/execute` | Execute approved operation |
| `POST /security/scans` | Run Trivy/Grype/Snyk/CodeQL/OWASP scan |
| `GET /security/scans` | Scan history |
| `POST /gitops/sync` | Sync ArgoCD/Flux applications |
| `GET /gitops` | GitOps application list |

## Deployment strategies

Rolling, Recreate, Canary, and Blue/Green are modeled on `DeliveryDeployment.strategy`.
Production environments require approval by default (`DeliveryEnvironment.requires_approval`).

## Security gates

Scanners never block silently — every scan returns an `explain` field with
severity breakdown (Critical/High/Medium/Low), SBOM metadata, and license issues.

## AI Release Assistant

Tools in `app/ai/tools/delivery.py`:

| Tool | Kind | Example |
|------|------|---------|
| `delivery.explain_failure` | read | "Why did deployment fail?" |
| `delivery.generate_release_notes` | read | "Generate release notes for 1.2.0" |
| `delivery.predict_risk` | read | "Predict deployment risk" |
| `delivery.recommend_rollback` | read | "Should we rollback?" |
| `delivery.propose_deployment` | approval | "Deploy checkout 1.2.0 to staging" |

All recommendations reference real deployment/pipeline evidence.

## Events

`RepositoryConnected`, `PipelineStarted`, `PipelineCompleted`, `DeploymentStarted`,
`DeploymentSucceeded`, `DeploymentFailed`, `ReleaseCreated`, `ReleaseApproved`,
`ReleaseCompleted`, `ArtifactPublished`, `GitOpsSyncCompleted`

## UI

Routes under `/delivery`: Dashboard, Repositories, Pipelines, Deployments,
Releases, GitOps, Security, DORA, Operations.

## Configuration

- `DELIVERY_ENABLED=true` (default)
- Migration `0023_delivery` → `0032_release_reliability` (Sprint 65F)

---

# Release Reliability (Sprint 65F)

Extends Delivery with progressive delivery, health gates, promotion policies, and rollback orchestration.

## Architecture

`ReleaseReliabilityService` composes:
- `DeliveryService` — releases, deployments, operations approval flow
- Observability/control-plane signals for health gates (no fabricated PASS)
- Security gate status from canonical findings
- Incident correlation on failed production verification

Tables use `rr_*` prefix. Records reference `dlv_releases`, `dlv_deployments`, `dlv_environments` — no duplication.

## Progressive delivery

Provider adapters: Argo Rollouts, Flagger, native K8s rolling, GitOps-controlled.
Modes: `live` | `offline` | `unavailable` — never claim live traffic shifting without validated provider.

All production mutations: propose → approval → execution via `DeliveryOperation`.

## Health gates

Outcomes: `PASS`, `WARN`, `FAIL`, `INSUFFICIENT_EVIDENCE`.
Production: insufficient evidence blocks promotion; WARN treated as FAIL.

## APIs (`/v1/delivery/release-reliability/*`)

`GET/POST /release-reliability`, verify, evidence, propose-rollout, pause/resume/promote/abort/rollback, history, promotion-policies, promotion-queue, freeze-windows, release-analytics.

## AI tools (grounded, read-only)

`release.assess_readiness`, `release.explain_gate_failure`, `release.recommend_strategy`, `release.compare_baseline`, `release.suggest_rollback`, `release.summarize_release`, `release.predict_blast_radius`

## Events & metrics

`ReleaseVerificationStarted/Passed/Failed`, `HealthGateEvaluated`, `RolloutProposed/Promoted/Paused/Aborted`, `RollbackRecommended/Executed`, `PromotionRequested/Blocked`, `FreezeWindowStarted/Ended`

`nexora_release_verification_total`, `nexora_release_health_gate_total`, `nexora_release_rollout_total`, `nexora_release_rollback_total`, `nexora_release_promotion_total`, `nexora_release_freeze_window_active`, `nexora_release_change_failure_rate`
