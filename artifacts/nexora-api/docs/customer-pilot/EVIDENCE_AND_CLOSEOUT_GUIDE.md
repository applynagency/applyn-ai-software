# Evidence and Closeout Guide

## Evidence view

The **Evidence** page shows customer-safe, redacted information:

- Before and after resource state (sensitive fields removed)
- Verification outcome: `VERIFIED`, `VERIFICATION_FAILED`, `INSUFFICIENT_EVIDENCE`, or `PENDING`
- Kubernetes and Prometheus summaries when applicable
- Audit timeline (internal metadata stripped)
- Approval package and decision record
- Rollback outcome if one occurred

## Exports

From `/v1/customer-pilot/operation/{id}/evidence/export` or the portal **Export evidence pack** button:

| Format | Description |
|--------|-------------|
| JSON | Structured evidence pack |
| Markdown | Human-readable report |
| HTML | Formatted report |
| PDF | Base64-encoded PDF (when export passes safety scan) |

Exports include organization-safe naming, pilot scope, operation summary, approval, execution status, verification evidence, known gaps, and closeout recommendation.

**Safety:** A redaction scan runs before export. If potential secrets are detected, export is blocked and `export_blocked: true` is returned.

## Closeout eligibility

Customers may request closeout when:

- The operation is `VERIFIED`, **or** the pilot ended without an operation (documented decision)
- Evidence pack exists
- Mandatory pilot stages (except `COMPLETE`) are complete
- No active operation or pending approval exists

## Closeout request

`POST /v1/customer-pilot/closeout/request` captures:

- Customer outcome rating (optional)
- Customer comments
- Named sign-off contact
- Whether follow-up is requested
- Optional `documented_no_operation` flag

This creates a `PENDING_OPERATOR_REVIEW` record. It does **not** advance the pilot to `COMPLETE`.

## Closeout statuses (customer view)

| Status | Meaning |
|--------|---------|
| `ELIGIBLE` | Prerequisites met; you may submit a request |
| `PENDING_OPERATOR_REVIEW` | Request submitted; awaiting Nexora operator |
| `CLOSED` | Operator completed closure via internal flow |
| `BLOCKED` | Prerequisites not met (see blockers list) |

Platform operators complete closure through the existing internal Pilot Center closure flow after reviewing the customer request.
