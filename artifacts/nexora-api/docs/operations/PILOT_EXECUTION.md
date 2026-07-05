# Pilot Execution (Sprint 66B)

Executable pilot workflow for the first real non-production customer pilot.

## Stages (strict order)

`CONNECT` → `VALIDATE` → `READ_ONLY_ASSESSMENT` → `BASELINE_CAPTURE` → `PROPOSE_OPERATION` → `CUSTOMER_APPROVAL` → `EXECUTE` → `VERIFY` → `COMPLETE`

Stages are persisted in `pilot_stages`. Explicit advancement via `POST /v1/pilot/execution/stages/{stage_key}/advance` enforces ordering (no skips). Automatic hooks from readiness, assessment, and live-operation flows complete stages when prerequisites are satisfied.

## Safe operation catalog

Allowlisted non-production operations only (see `app/pilot/operations.py`):

- Kubernetes diagnostics (read-only)
- Restart / scale deployment (mutation, reversible)
- Read deployment logs/events (read-only)
- GitHub pipeline sync (read-only)
- Prometheus health/SLO query (read-only)

All mutations pass `LiveMutationGate`, customer approval, typed confirmation, cooldown, operation limits, and kill switch.

## Customer approval

`POST /v1/pilot/approvals` records approver name/email, summary, environment, rollback plan, expiry, and payload hash. Approval is invalidated if the operation payload changes. Production targets are rejected.

## Verification

Post-execution verification collects before/after evidence and sets `VERIFIED`, `VERIFICATION_FAILED`, or `INSUFFICIENT_EVIDENCE`. Results are labeled `LIVE`, `SIMULATED`, `OFFLINE`, or `UNAVAILABLE`. Success is never reported without evidence.

## Evidence pack

`GET /v1/pilot/evidence-pack/export` returns redacted JSON, Markdown, and HTML including stages, approvals, operations, verification, and audit references.

## Safety controls

- `PILOT_MODE_ENABLED` + organization allowlist
- Non-production environment classification required
- Per-enrollment operation limit and mutation cooldown
- Kill switch: `POST /v1/pilot/safety/kill-switch`

## Migration

Alembic revision `0035_pilot_execution` adds `pilot_stages`, `pilot_approvals`, and execution columns on enrollments/live operations.
