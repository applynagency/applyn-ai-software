# Customer Evidence Guide

## Purpose

Evidence demonstrates what the environment looked like **before** and **after** the pilot operation, supporting audit, verification, and closure.

## Before operation (required)

Collect and retain:

| Evidence type | Content |
|---------------|---------|
| Integration health | Connection state, validation timestamp, capability summary (redacted) |
| Deployment state | Desired/available/ready replicas, pod list, restart counts |
| Metrics baseline | Replica-count or availability series for target deployment |
| Events | Recent warning/error events in pilot namespace |
| Repository metadata | Branch, last commit summary (read-only) |
| Proposal record | Action, resource name, parameters, preflight summary, payload hash |

## After operation (required)

| Evidence type | Content |
|---------------|---------|
| Execution result | Action outcome, correlation ID, timestamp |
| Deployment state | Post-scale replica counts, rollout status |
| Metrics | Post-change metric value aligned with target replicas |
| Events | Rollout-related events during change window |
| Verification verdict | `VERIFIED`, `VERIFICATION_FAILED`, or `INSUFFICIENT_EVIDENCE` with reasons |

## Evidence pack export

Use the platform evidence pack export endpoint to download a redacted bundle suitable for customer retention. Sensitive fields (tokens, kubeconfig, API keys) are removed automatically.

## Insufficient evidence

If collectors return errors (e.g. permission denied, metrics unavailable, malformed response):

- Verification status is **`INSUFFICIENT_EVIDENCE`**
- **Automatic rollback does not occur** for insufficient evidence alone
- Remediate collector access and re-run verification, or close without advancing if no mutation occurred

## Positive verification failure

If evidence **confirms** an unhealthy state (e.g. replica mismatch, failed rollout):

- Verification status is **`VERIFICATION_FAILED`**
- Rollback **may** proceed per the documented rollback plan and operator authorization

## Retention

- Customer: retain evidence pack for your compliance period
- Platform: audit log entries retained per service agreement

## Redaction

Never include in customer-shared evidence:

- Raw credentials or kubeconfig
- Internal hostnames not agreed for disclosure
- Unrelated namespace or cluster data
