# Customer Pilot Portal — Operations Guide

Sprint 67B introduces a customer-facing portal for scoped non-production pilot operations. This document is for platform operators and engineering.

## Scope

- **Non-production only** — production environments are rejected at every API boundary.
- **Organization-scoped** — all `/v1/customer-pilot/*` endpoints require org context; cross-tenant access returns 404.
- **Customer approval ≠ execution** — customers approve or reject proposals; execution still requires an authorized platform operator plus typed confirmation.
- **No provider mutation from customer routes** — customer APIs are read-mostly except approval decisions and closeout requests.

## Migration

- **Head:** `0037_customer_pilot_portal` (chains from `0036_integration_onboarding`)
- **New tables:**
  - `pilot_approval_packages` — immutable approval package snapshots
  - `pilot_closeout_requests` — customer closeout requests (`PENDING_OPERATOR_REVIEW`; does not advance `COMPLETE`)

## API Surface

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/v1/customer-pilot/overview` | Portal visibility, scope, safety, status |
| GET | `/v1/customer-pilot/readiness` | Launch readiness (customer-safe) |
| GET | `/v1/customer-pilot/timeline` | Stage timeline |
| GET | `/v1/customer-pilot/operation` | Current operation |
| GET | `/v1/customer-pilot/operation/{id}` | Operation detail |
| GET | `/v1/customer-pilot/operation/{id}/approval-package` | Immutable approval package |
| POST | `/v1/customer-pilot/operation/{id}/approval/decide` | Customer admin approve/reject |
| GET | `/v1/customer-pilot/operation/{id}/execution-status` | Execution gates (read-only) |
| GET | `/v1/customer-pilot/operation/{id}/verification` | Verification outcome |
| GET | `/v1/customer-pilot/operation/{id}/evidence` | Redacted evidence view |
| GET | `/v1/customer-pilot/operation/{id}/evidence/export` | JSON/Markdown/HTML/PDF export |
| GET | `/v1/customer-pilot/closeout` | Closeout eligibility and status |
| POST | `/v1/customer-pilot/closeout/request` | Request operator closeout review |
| GET | `/v1/customer-pilot/notifications` | Customer pilot inbox |
| POST | `/v1/customer-pilot/notifications/{id}/read` | Mark notification read |

**Operator-only (internal Pilot Center):**

| GET | `/v1/pilot/live-operations/{id}/operator-handoff` | Read-only handoff summary; re-runs readiness |

## Approval Invalidation

Customer approval is invalidated when:

- Operation payload changes (hash mismatch)
- Rollback plan changes
- Environment changes to production
- Integration readiness becomes stale, disconnected, degraded, or reauth-required
- Approval expires

Statuses: `PENDING`, `APPROVED`, `REJECTED`, `EXPIRED`, `INVALIDATED`.

Re-approval requires a new proposal and new immutable package snapshot.

## Operator Handoff

After customer approval, handoff status is computed at retrieval time:

- `READY` — all gates pass, ready for typed confirmation
- `BLOCKED` — blockers present (e.g. rejected approval, kill switch)
- `INSUFFICIENT_EVIDENCE` — evidence gaps flagged

Handoff includes customer approval details, operation, rollback plan, integration readiness, before-state evidence, typed confirmation text, and verification checklist. **No execute/confirm endpoints on customer portal.**

## Notifications

Uses `InboxNotification` with category `customer_pilot`. Deep links target `/customer-pilot/*` routes.

## UI Routes

- `/customer-pilot` — overview
- `/customer-pilot/readiness`
- `/customer-pilot/operation`
- `/customer-pilot/approval`
- `/customer-pilot/execution`
- `/customer-pilot/evidence`
- `/customer-pilot/closeout`

Nav item **Customer Pilot** appears when `portal_visible` is true (active enrollment or eligible customer admin).

## Safety Confirmation

This sprint adds **no** provider mutation paths. All customer portal requests are read-only or audit-logged decisions. Execution remains on internal Pilot Center with `LiveMutationGate` and two-step confirmation unchanged.
