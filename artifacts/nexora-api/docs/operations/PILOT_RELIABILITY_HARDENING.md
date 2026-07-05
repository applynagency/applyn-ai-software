# Pilot Reliability Hardening (Sprint 66K)

## Purpose

Eliminate remaining pilot API test failures, make stage/approval/export behavior deterministic across SQLite and PostgreSQL, and prepare customer-facing non-production pilot materials. **No customer infrastructure or provider mutation** in this sprint.

## Failure classification and root causes

| Test | Root cause category | Deterministic? | Backend | Fix |
|------|---------------------|----------------|---------|-----|
| `test_pending_approval_does_not_complete_customer_stage` | Stage seed/advance idempotency + fixture isolation | Order-dependent flake | SQLite (both semantics) | Seed integrations; mock collectors in `run_pilot_prereqs`; `_complete_stage_required` raises on incomplete prereqs; assert prior stages in `_propose_with_safety` |
| `test_decide_pending_approval_and_execution_readiness` | Approval state persistence + stage seed | Order-dependent flake | SQLite | Same prereq seeding; `decide_customer_approval` uses `_complete_stage_required`; `get_execution_status` refreshes enrollment |
| `test_live_operation_two_step_confirmation` | Export serialization / preflight metadata | Deterministic after prereq fix | SQLite | Add `resource_name` to proposal preflight JSON; approval must be `APPROVED` before confirm (`approve: true` or decide flow) |
| `test_export_pilot_report` | Fixture isolation (assessment not persisted) | Deterministic | SQLite | `run_pilot_prereqs` + onboarding before `assessment/run`; `export_report` includes execution status |

All four failures were **related to Sprint 66J adjacent code paths** (stricter stage completion and closure/export), not unrelated pre-existing defects.

## Product changes

### `app/services/pilot_execution.py`

- `_complete_stage_required()` — propagates `ValidationError` instead of swallowing
- `_propose_with_safety()` — asserts CONNECT→BASELINE_CAPTURE completed; enriches preflight with `resource_name`, `resource_id`, `namespace`, `action`
- `create_customer_approval` / `decide_customer_approval` — deterministic stage completion for `CUSTOMER_APPROVAL`
- `get_execution_status()` — `session.refresh(enrollment)` before read

### `app/tests/pilot_fixtures.py`

- `seed_pilot_integrations()` — CONNECTED K8s, GitHub, Prometheus with correct capabilities
- `run_pilot_prereqs()` — mocked collectors for deterministic assessment/baseline completion

### `app/pilot/launch_readiness.py`

- Read-only evaluator: `GO` / `NO_GO` / `INSUFFICIENT_EVIDENCE`

### API / UI

- `GET /v1/pilot/launch-readiness`
- Pilot Center: Customer Launch Readiness panel (`static/app.js`)

## Regression tests

`app/tests/test_pilot_reliability_hardening.py`:

- Stage seed stability across repeated reads
- Approval decision enrollment linkage
- Payload hash invalidation
- Export for fresh enrollment
- Closure blocked without evidence
- Cross-org launch readiness isolation
- Launch readiness no mutation side effects
- Rollback safety semantics unchanged

## Validation results (Sprint 66K close)

| Suite | Result |
|-------|--------|
| `test_pilot_readiness.py` | 14 passed |
| `test_pilot_execution.py` | 15 passed |
| `test_pilot_rollback_safety.py` | 7 passed |
| `test_live_preflight_enforcement.py` | 14 passed |
| `test_integration_readiness.py` | 22 passed |
| `test_postgres_migration_chain.py` | 2 passed, 1 skipped |
| Combined pilot + live preflight | 67 passed |

No new Alembic migrations. PostgreSQL migration chain unchanged.

## Artifacts

`artifacts/pilot-reliability-hardening/`

## Boundaries preserved

- No weakening of approval, typed-confirmation, environment, integration-readiness, or rollback safety gates
- No customer credentials, organizations, or infrastructure connected
- Internal pilot remains CLOSED (`INTERNAL_NON_PRODUCTION_LIVE_PILOT_VERIFIED`)
