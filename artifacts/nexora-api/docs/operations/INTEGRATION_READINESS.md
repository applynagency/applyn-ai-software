# Integration Readiness (Sprint 65G)

Production-grade integration validation, credential health monitoring, capability-based authorization, and live-operation preflight checks.

## Scope

Cross-platform operational readiness layer on top of existing connection stores:

- Marketplace connections (`integration_connections`)
- Observability integrations (`obs_integrations`)
- Security providers (`sec_providers`)
- Deployment credentials (via credential references only)

Does **not** duplicate Secret Manager, approval workflows, or domain engines.

## Lifecycle States

`DRAFT` → `VALIDATING` → `CONNECTED` | `DEGRADED` | `FAILED` | `DISCONNECTED` | `EXPIRED` | `REAUTH_REQUIRED`

## API (`/v1/integrations/*`)

| Endpoint | Purpose |
|----------|---------|
| `GET /providers` | Per-provider health summary |
| `GET /connections/readiness` | Readiness-enriched connection list |
| `POST /connections/{id}/validate` | Run validation probe |
| `GET /connections/{id}/capabilities` | Capability matrix + write allowance |
| `GET /connections/{id}/health` | Current health snapshot |
| `GET /connections/{id}/history` | State transition history |
| `GET /connections/{id}/expiry` | Credential expiry reminders |
| `POST /connections/{id}/acknowledge-expiry` | Acknowledge reminder |
| `POST /connections/{id}/snooze-expiry` | Snooze reminder |
| `GET /dashboard` | Org-wide readiness dashboard |
| `POST /notifications/test` | Dry-run notification validation |

Domain CRUD remains on existing marketplace/observability/security APIs.

## Live Operation Safety

Before any live mutation, `preflight_live_operation` requires:

- State `CONNECTED`
- Provider mode `live`
- Required capabilities validated
- Valid credential reference
- Approval satisfied
- Organization match
- Idempotency key

Failed preflight **never** falls back to simulation. Simulation requires `explicit_simulation=True`.

## Scheduler

`INTEGRATION_READINESS_ENABLED` (default `true`) starts `integration_health_loop` with leader election (`scheduler_lock("integration_health")`).

- Interval: `INTEGRATION_HEALTH_INTERVAL_SECONDS` (default 300s)
- Consecutive failure threshold: `INTEGRATION_HEALTH_FAILURE_THRESHOLD` (default 3)

## Release Reliability Integration

Health gates in production require live observability source modes (`metrics`, `logs`). Offline/unavailable sources yield `INSUFFICIENT_EVIDENCE` and block promotion.

## Validation Report (CI / test environment)

| Integration | Test mode |
|-------------|-----------|
| Marketplace providers | Offline/mocked via injectable probes |
| Kubernetes | Offline validator probes (no real cluster) |
| Trivy/Gitleaks/Semgrep/Checkov | PATH binary check only |
| Prometheus/Loki/Tempo | Endpoint metadata check (no live query in CI) |
| Notifications | Dry-run only (`dry_run=true`) |

**Live mutations executed in CI:** None  
**Production traffic shifting tested live:** No
