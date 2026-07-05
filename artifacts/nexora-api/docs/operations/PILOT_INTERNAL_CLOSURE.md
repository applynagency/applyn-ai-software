# Internal Pilot Closure (Sprint 66J)

## Purpose

Close the internal non-production pilot after read-only final verification, preserving an
immutable evidence trail and confirming rollback safety semantics. **No infrastructure
mutation occurs in this sprint.**

## Preconditions

| Item | Value |
|------|-------|
| Organization | `41a17fb0-9d64-4e84-accf-0c81f6dc87c4` |
| Enrollment | `2c0ce636-4f82-420d-8321-8a4c6f1ed754` |
| Operation | `30d98614-5fc6-4410-a28c-e65a15eeabc7` |
| Deployment | `pilot-demo` in `nexora-pilot` |
| VERIFY stage | `COMPLETED` with `VERIFIED` |
| COMPLETE stage | `PENDING` until closure |

## Rollback safety invariant (66J fix)

Rollback may occur **only** when verification produces a positive, evidence-backed
`VERIFICATION_FAILED` result:

- `INSUFFICIENT_EVIDENCE` — missing collectors, PermissionError, Prometheus unavailable,
  malformed responses, incomplete data — **never** triggers rollback.
- Rollback decisions record `failed_verification_rules` and supporting evidence.

Code: `app/pilot/verification.py`, `app/services/pilot_execution.py`

Tests: `app/tests/test_pilot_rollback_safety.py`

## Historical safety incident (preserved)

During Sprint 66I, the first verify pass collected a `PermissionError` for Kubernetes
evidence. Pre-fix logic incorrectly returned `VERIFICATION_FAILED` and triggered rollback
(2→1). The incident is preserved in `operation-timeline.json` and is **not** overwritten.

## Closure API

```
POST /v1/pilot/closure
```

Read-only body: `kubernetes_evidence`, `prometheus_evidence`, `events_evidence`,
`integration_evidence`.

Advances only the `COMPLETE` stage when:

1. Exactly one operation exists and is `SUCCEEDED` / `VERIFIED`
2. VERIFY stage is `COMPLETED`
3. Live read-only evidence confirms 2/2 replicas, healthy pods, Prometheus metric, CONNECTED integration
4. Regression suite passes

Outcome: `INTERNAL_NON_PRODUCTION_LIVE_PILOT_VERIFIED`

## Execute closure

```bash
cd artifacts/nexora-api
docker compose -f docker-compose.yml -f docker-compose.pilot-internal.yml build api
docker compose -f docker-compose.yml -f docker-compose.pilot-internal.yml up -d

docker compose -f docker-compose.yml -f docker-compose.pilot-internal.yml \
  exec -u 0 api python scripts/pilot_sprint66j_closure.py
```

Artifacts: `artifacts/pilot-internal-closure/`

## Regression suite

```bash
pytest app/tests/test_pilot_rollback_safety.py -q
pytest app/tests/test_pilot_execution.py -q
pytest app/tests/test_pilot_readiness.py -q
pytest app/tests/test_live_preflight_enforcement.py -q
pytest app/tests/test_integration_readiness.py -q
pytest app/tests/test_migration_check.py -q
```

## Hard boundaries

- No confirm, execute, rollback, scale, or K8s write paths
- No RBAC, credential, or kill-switch changes
- No simulation
- Internal Docker pilot stack only
