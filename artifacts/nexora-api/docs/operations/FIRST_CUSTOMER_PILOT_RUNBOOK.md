# First Customer Pilot Runbook

This runbook defines the exact process for Nexora's first real customer pilot.

## Phase 1 - Before customer access

1. Deploy migration `0035_pilot_execution` (includes `0034_pilot_readiness`).
2. Set `PILOT_MODE_ENABLED=true`.
3. Keep `PILOT_MODE_ALL_ORGS=false`.
4. Add only the selected pilot organization UUID to `PILOT_ORGANIZATION_IDS`.
5. Verify backup and restore status before enabling pilot access.
6. Verify audit logging, notification channel delivery, support token flow, and admin MFA.
7. Confirm production mutation policies remain disabled.

## Phase 2 - Connect a safe non-production environment

Recommended first path: `Kubernetes + GitHub + Prometheus`

Requirements:

- Non-production Kubernetes cluster only.
- Dedicated service account with minimum required RBAC.
- GitHub token or GitHub App restricted to one pilot repository.
- Prometheus read-only query credentials.
- No production kubeconfig, cloud credentials, or deployment credentials.

## Phase 3 - Validate integrations

1. Register the required connections.
2. Run readiness validation.
3. Record the discovered capabilities.
4. Resolve RBAC and capability gaps before proceeding.
5. Confirm every required integration shows `CONNECTED` and `LIVE` only after a real probe succeeds.
6. If a probe fails, keep the connection in `FAILED` or `DEGRADED`; never force `CONNECTED`.

## Phase 4 - Read-only assessment

1. Run the Pilot Center assessment.
2. Review Kubernetes health, pipelines, deployments, alerts, SLOs, security, costs, and integration gaps.
3. Export the pilot report.
4. Confirm citations and evidence are present.
5. Capture the baseline scorecard.

## Phase 5 - First safe live operation

Allowed action: restart or scale one explicitly selected non-production Kubernetes deployment.

Required sequence:

1. Enable pilot live operations.
2. Propose the operation.
3. Confirm the resource and environment details.
4. Type the exact resource name.
5. Approve through the normal approval workflow.
6. Confirm `LiveMutationGate` passes.
7. Execute the operation.
8. Verify post-operation health.
9. Record evidence, audit event, activity entry, and rollback guidance.
10. Capture user feedback.

Production must never be selected or operated in this runbook.

## Sprint 66B execution stages

Walk Pilot Center stages in strict order (no skips):

`CONNECT` → `VALIDATE` → `READ_ONLY_ASSESSMENT` → `BASELINE_CAPTURE` → `PROPOSE_OPERATION` → `CUSTOMER_APPROVAL` → `EXECUTE` → `VERIFY` → `COMPLETE`

See `PILOT_EXECUTION.md` for API endpoints, approval workflow, verification rules, and evidence pack export.

## Phase 6 - Pilot success criteria

A pilot is successful only if all are true:

- At least one real integration is connected and validated.
- Read-only assessment completed using live evidence.
- At least one approved non-production operation completed.
- Post-operation verification completed.
- Audit and evidence records exist.
- No secret exposure.
- The customer confirms the platform produced useful operational value.
