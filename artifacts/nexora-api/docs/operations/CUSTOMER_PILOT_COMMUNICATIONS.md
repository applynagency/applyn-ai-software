# Customer Pilot Communications — Operations Guide

Sprint 67C adds customer-safe communications, unified timeline, approval reminders, and notification preferences on top of the Sprint 67B Customer Pilot Portal.

## Migration

- **Head:** `0038_customer_pilot_communications` (chains from `0037_customer_pilot_portal`)
- **Tables:**
  - `pilot_customer_communications` — draft/sent/cancelled messages
  - `pilot_communication_comments` — rate-limited customer comments
  - `pilot_notification_preferences` — per-user delivery preferences
  - `pilot_approval_reminder_deliveries` — durable reminder dedupe

## Cron job

- **Task:** `cron_customer_pilot_approval_reminders`
- **Interval:** `JOB_CRON_CUSTOMER_PILOT_APPROVAL_REMINDERS_SECONDS` (default 300s)
- **Lock:** `scheduler_lock("customer_pilot_approval_reminders")` + Arq `unique=True`
- **Behavior:** 24h and 1h reminders for `PENDING` approvals; expiry notification after expiration; no auto-approve/extend

## Metrics

- `nexora_customer_pilot_approval_reminders_total{reminder_type}`
- `nexora_customer_pilot_approval_reminder_failures_total`
- `nexora_customer_pilot_approval_expirations_total`

## APIs

### Customer (`/v1/customer-pilot/*`)

| Endpoint | Purpose |
|----------|---------|
| GET `/timeline` | Unified event timeline (keyset pagination, filters) |
| GET `/timeline/export` | JSON/Markdown/HTML/PDF export |
| GET `/communications` | Sent messages |
| GET `/communications/{id}` | Message detail |
| POST `/communications/{id}/acknowledge` | Acknowledge receipt |
| POST `/communications/{id}/comment` | Plain-text comment (rate limited) |
| GET/PUT `/notification-preferences` | Delivery preferences |

### Operator (`/v1/pilot/*`)

| Endpoint | Purpose |
|----------|---------|
| GET `/communications/templates` | Template catalog |
| POST `/communications/draft` | Create draft |
| POST `/communications/{id}/send` | Send after validation |
| POST `/communications/{id}/cancel` | Cancel draft |

## Guardrails

- No provider mutation from any endpoint or cron job
- Operator messages validated before send (no false VERIFIED/LIVE claims)
- All payloads redacted via `sanitize_customer_view`
- Timeline excludes internal audit actions (`pilot.confirmation_*`, credentials, tokens)

## Safety confirmation

This sprint adds **no** execution, confirmation, rollback, or provider mutation paths.
