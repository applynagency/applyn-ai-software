# Customer Integration Onboarding (Operations)

## Purpose

Sprint 67A enables authorized customer admins to connect and validate non-production Kubernetes, source-control, and Prometheus-compatible integrations through a guided wizard. **Onboarding and validation only** — no pilot operations, approvals, stage advancement, or provider mutations.

## Data model

**Table:** `int_onboarding_sessions` (migration `0036_integration_onboarding`)

**Lifecycle:** `DRAFT` → `CREDENTIALS_ADDED` → `VALIDATING` → `VALIDATED` → `READY_FOR_PILOT` | `FAILED` | `REAUTH_REQUIRED` | `CANCELLED`

Final `int_connection_registry` rows are created **only after successful validation**, not on session create.

## API surface

Prefix: `/v1/onboarding/integrations`

| Method | Path | Role |
|--------|------|------|
| GET | `/providers` | List supported providers |
| POST | `/sessions` | Create session (admin) |
| GET | `/sessions` | List org sessions |
| GET | `/sessions/{id}` | Session detail |
| PUT | `/sessions/{id}/environment` | Declare environment + scope |
| POST | `/sessions/{id}/credentials` | Store credential ref (SecretManager) |
| POST | `/sessions/{id}/validate` | Run read-only validation |
| GET | `/sessions/{id}/rbac-report` | RBAC gap report |
| GET | `/sessions/{id}/least-privilege-guide` | RBAC YAML guidance |
| POST | `/sessions/{id}/acknowledge` | Mark READY_FOR_PILOT |
| POST | `/sessions/{id}/cancel` | Cancel session |
| GET | `/sessions/{id}/evidence` | Redacted evidence export |
| GET | `/readiness` | Consolidated pilot readiness |
| GET | `/customer-pilot-prerequisites` | Prerequisite checklist |

## Security boundaries

- Production classification rejected for pilot onboarding
- Namespace-scoped Kubernetes only; no wildcards
- Single repository for source control
- Read-only Prometheus queries
- Prohibited K8s permissions detected via SSAR (secrets, exec, port-forward, nodes, delete)
- Secrets never returned in API, UI, audit, or evidence
- Organization admin (`can_manage_organization`) required for writes

## Events

`IntegrationOnboardingStarted`, `IntegrationCredentialStored`, `IntegrationValidationStarted/Succeeded/Failed`, `IntegrationScopeRejected`, `IntegrationRBACGapDetected`, `IntegrationOnboardingCancelled`, `CustomerPilotReadinessEvaluated`

## Metrics

`nexora_onboarding_sessions_total`, `nexora_onboarding_validation_total`, `nexora_onboarding_validation_duration_seconds`, `nexora_onboarding_rbac_gap_total`, `nexora_onboarding_readiness_total`

## UI

**Customer Onboarding** nav entry → `/customer-onboarding` (Pilot Center module)

## Tests

`app/tests/test_integration_onboarding.py`

## Related docs

- `docs/customer-pilot/INTEGRATION_ONBOARDING_GUIDE.md`
- `docs/operations/CUSTOMER_PILOT_LAUNCH.md`
