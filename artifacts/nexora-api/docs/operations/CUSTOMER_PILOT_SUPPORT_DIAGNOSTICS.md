# Customer Pilot Support Diagnostics

Read-only support bundle for operator handoff and incident investigation.

## Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /v1/pilot/support/diagnostics` | Enriched diagnostics view (integration + operations + notification health) |
| `GET /v1/pilot/support/diagnostics/export` | Full support bundle in JSON, Markdown, HTML, PDF |

## Bundle contents (redacted)

- Pilot enrollment and stage state
- Launch readiness verdict and failed checks
- Operations readiness verdict and failed checks
- Notification delivery health summary
- Approval / operation status summaries
- Recent customer-safe timeline events
- Recent internal support-safe audit events
- Migration version and feature-flag state

## Excluded (never exported)

- Secrets, tokens, kubeconfigs, credentials
- Raw HTTP headers or provider responses
- Internal network addresses
- Full stack traces
- Unrelated tenant data

## Redaction

All payloads pass through `sanitize_customer_view()`. Export runs `assert_export_safe()` and **fails closed** if secrets are detected (`export_blocked: true`).

## Safe sharing procedure

1. Generate bundle from customer's organization context (tenant-scoped)
2. Use export endpoint — prefer JSON for ticketing systems
3. Verify `redacted: true` and `export_blocked: false`
4. Share only the Markdown or PDF export — never raw database dumps
5. Record `CustomerPilotSupportBundleGenerated` event in audit review

## Tenant isolation

Bundles are scoped to `org_context.requires_organization`. Cross-tenant data never appears.

## UI

Pilot Center → Operations health → **Export support bundle**

## Metric

- `nexora_customer_pilot_support_bundle_total`

## Event

- `CustomerPilotSupportBundleGenerated`

## Database issue

- Evidence exports and delivery state changes fail closed
- Read-only portal uses existing availability/error conventions

## Rollback reference

See `CUSTOMER_PILOT_OPERATIONS_READINESS.md` for migration downgrade to `0038`.
