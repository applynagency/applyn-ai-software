# Pilot Readiness (Sprint 66A)

Production pilot onboarding for the Nexora DevOps/SRE platform. Pilot Center is gated by `PILOT_MODE_ENABLED` and optional `PILOT_ORGANIZATION_IDS`.

## API (`/v1/pilot/*`)

| Endpoint | Purpose |
|----------|---------|
| `GET /readiness` | Checklist state and score |
| `POST /readiness/check` | Auto-detect completion from GA + integration readiness |
| `GET /onboarding-paths` | Four guided integration paths (K8s/GitHub/Prometheus variants) |
| `POST /onboarding-paths/{id}/start` | Select onboarding path |
| `GET /assessment` | Latest read-only assessment |
| `POST /assessment/run` | Run cited, read-only assessment |
| `GET /scorecard` | Pilot baseline metrics and scores |
| `POST /live-operations/enable` | Enable controlled live ops (readiness ≥ 60) |
| `POST /live-operations` | Propose non-production mutation (step 1) |
| `POST /live-operations/{id}/confirm` | Typed confirmation + approval (step 2) |
| `GET /support/diagnostics` | Capability/RBAC troubleshooting |
| `GET /report/export` | Redacted pilot report bundle |

## Safety

- Production environments are rejected for pilot live operations.
- `LiveMutationGate.preflight_mutation()` is mandatory on confirm.
- Secrets are never returned in API responses; support bundles use GA redaction.
- Simulation is explicit only — no silent fallback to offline mode.

## Validation status

All automated tests use offline/mock adapters. No real customer infrastructure was connected during Sprint 66A implementation. Do not claim production readiness until a real pilot completes: connect → validate → assessment → approved non-production operation → verification.
