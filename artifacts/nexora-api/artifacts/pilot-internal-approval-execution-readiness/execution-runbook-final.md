# APPROVED FOR INTERNAL PILOT — NOT EXECUTED — TYPED CONFIRMATION REQUIRED

# Operator Execution Runbook (future step — not executed in Sprint 66G)

**PROPOSED ONLY — NOT APPROVED — NOT EXECUTED**

Prerequisites:
- Customer approval status is APPROVED and not expired
- Payload hash matches proposal
- Kill switch is false; operation limit and cooldown satisfied
- Integration validation is fresh (CONNECTED + live)

Steps (later sprint only):
1. Confirm operation `30d98614-5fc6-4410-a28c-e65a15eeabc7` with typed resource name `pilot-demo`
2. LiveMutationGate preflight runs with approval_satisfied=true
3. Kubernetes scale patch applied via pilot integration
4. Post-operation verification against criteria
5. Idempotency key: `sprint66g-pilot-demo-scale-1-to-2-v1`