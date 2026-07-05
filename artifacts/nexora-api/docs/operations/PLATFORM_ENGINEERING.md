# Platform Engineering (Sprint 64A)

Infrastructure as Code and environment factory — extends the Control Plane without duplicating it.

Package: `app/platform_engineering/`. Service: `app/services/platform_engineering.py`.

## API (`/v1/platform-engineering`)

| Area | Endpoints |
|------|-----------|
| Dashboard | `GET /dashboard` |
| IaC | `GET/POST /repositories`, `/stacks`, `/runs`, `POST /stacks/{id}/runs`, `POST /runs/{id}/decide` |
| Templates | `GET /templates` |
| Environment Factory | `GET/POST /environments`, `POST /environments/{id}/decide` |
| Provisioning | `GET/POST /provisions`, `POST /provisions/{id}/decide` |
| Secrets | `GET/POST /secrets`, `POST /secrets/{id}/rotate` (references only) |
| Catalog | `GET /catalog`, `POST /catalog/requests`, `POST /catalog/requests/{id}/decide` |
| Golden Templates | `GET/POST /golden-templates` |
| Compliance | `POST /compliance/scan`, `GET /compliance/latest` |
| Drift | `POST /drift/scan`, `GET /drift`, `POST /drift/{id}/acknowledge` |
| AI | `GET /ai-context` |

## IaC providers

Terraform, OpenTofu, Pulumi, CloudFormation, Azure Bicep — via `app/platform_engineering/iac/registry.py`.

Operations: VALIDATE, FMT, PLAN, APPLY, DESTROY, IMPORT, REFRESH, GRAPH.

Apply/destroy/import require approval. Execution uses `ExecutionEngine`.

## Extends (does not duplicate)

- **Control Plane** — cloud accounts, clusters, policy findings for drift/compliance
- **Delivery** — GitOps apps for GitOps drift detection
- **Execution Engine** — long-running IaC jobs
- **Secret Manager** — credential resolution (values never exposed in API)
- **Event Bus** — domain events for provisioning and Terraform lifecycle
- **Copilot** — AI Platform Engineer tools

## Models (`pe_*` tables)

12 tables in migration `0025_platform_engineering`.

## Events

- `EnvironmentCreated`, `ProvisionStarted`, `ProvisionCompleted`
- `TerraformPlanGenerated`, `TerraformApplied`, `TerraformDriftDetected`
- `PlatformTemplateCreated`, `SecretRotated`

## Configuration

- `PLATFORM_ENGINEERING_ENABLED=true` (default)

## UI routes

- `/platform-engineering` — Dashboard
- `/platform-engineering/templates` — Platform templates
- `/platform-engineering/infrastructure` — IaC stacks & runs
- `/platform-engineering/provisioning` — Cluster provisioning
- `/platform-engineering/catalog` — Self-service catalog
- `/platform-engineering/secrets` — Secret references
- `/platform-engineering/drift` — Drift findings
- `/platform-engineering/compliance` — Compliance reports
