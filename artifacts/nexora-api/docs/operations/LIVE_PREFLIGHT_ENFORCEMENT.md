# Live Preflight Enforcement (Sprint 65H)

Mandatory integration readiness gate for every live infrastructure mutation.

## Central Gate

`LiveMutationGate.preflight_mutation()` in `app/integration_readiness/live_gate.py` is the single enforcement point. All domain execute boundaries call this before provider execution.

## Wired Domains

| Domain | Execute boundary | Preflight enforced |
|--------|------------------|-------------------|
| Control Plane | `ControlPlaneService.execute_operation` | Yes |
| Delivery | `DeliveryService.execute_operation` | Yes |
| Release Reliability | `ReleaseReliabilityService._rollout_action` | Yes (live mode) |
| Platform Engineering | `PlatformEngineeringService._execute_run` | Yes |
| Security Platform | `SecurityPlatformService.execute_remediation` | Yes |

## Behavior

- **Blocked:** Operation fails with structured `integration_readiness` context; evidence persisted to `int_live_evidence`; audit + events emitted.
- **Explicit simulation:** `params.explicit_simulation=true` bypasses live checks; result labeled `simulated: true`.
- **Never auto-fallback:** Failed live preflight does not downgrade to simulation.

## Validation Report (CI)

| Path | Test mode |
|------|-----------|
| Control Plane execute | Mock/offline registry; no real cluster |
| Delivery execute | Explicit simulation path |
| Release rollout | Offline provider_mode |
| IaC apply/destroy | SimulatedIaCProvider |
| Security remediation | Stub execution |

**Live mutations against real infrastructure:** None  
**Production traffic shifting tested live:** No
