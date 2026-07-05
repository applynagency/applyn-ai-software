# Customer Pilot Notification Recovery

Operational guide for notification delivery failures in the customer pilot communications and reminder system.

## Delivery states

| Status | Meaning |
|--------|---------|
| `queued` | Awaiting delivery |
| `sent` | Handed to provider |
| `delivered` | Confirmed delivery (in-app always; email when provider supports) |
| `failed` | Max retries exhausted |
| `retrying` | Exponential backoff in progress |
| `cancelled` | Operator or system cancelled |
| `suppressed_by_preference` | User preference blocked delivery |

## Idempotency

Each delivery uses a unique `idempotency_key` per communication/reminder + recipient + channel. Retries never create duplicate inbox or email records.

## Retry policy

- Exponential backoff from 60s base, capped at 3600s
- Maximum 5 attempts (`max_attempts`)
- Failed delivery does **not** affect approval status, timeline integrity, or pilot execution eligibility

## Requeue procedure

**Endpoint:** `POST /v1/pilot/communications/{communication_id}/deliveries/{delivery_id}/requeue`

Requirements:

- Operator write permission
- Delivery status must be `failed` or `cancelled`
- Cannot requeue reminder deliveries when linked approval is not `PENDING`
- Rate limited (20 requeues per organization per hour)
- Idempotent if already `queued`
- Audit event: `pilot.notification_delivery_requeued`
- Domain event: `CustomerPilotNotificationRequeued`

Steps:

1. Fix root cause (Redis, worker, SMTP)
2. Verify operations readiness: `GET /v1/pilot/operations-readiness`
3. Requeue failed delivery records only
4. Confirm delivery status moves to `queued` then `delivered`
5. Check customer timeline for customer-safe outcome language

## Redis outage

- Reminder cron skips when lock cannot be acquired (`skipped: lock_not_acquired`)
- No duplicate sends after recovery
- Operations readiness → `NO_GO`

## Worker outage

- Approvals remain `PENDING` until `expires_at`
- Customer sees degradation notice on readiness page
- Restart Arq worker on default queue; verify reminder cron registration

## Reminder cron failure

1. Check `pilot_scheduler_health_snapshots` for consecutive failures
2. Review worker logs for `cron_customer_pilot_approval_reminders`
3. Resolve Redis/worker issues
4. Wait for next cron cycle (default 300s)

## Email provider failure

- In-app notifications continue when preferences allow
- Timeline remains canonical source of truth
- Do not retry indefinitely — bounded at 5 attempts
- Configure `SMTP_HOST` for email channel recovery

## Approval nearing expiry with delayed notifications

- Approval expiry is enforced at API time and by reminder cron
- Delayed notifications do not extend approval window
- Customer communication template:

> We are experiencing a temporary delay in notification delivery. Your approval status and expiry time shown in the Customer Pilot portal remain authoritative. If your approval window is ending soon, please sign in to review your pending approval directly.

## Metrics

- `nexora_customer_pilot_notification_deliveries_total{status}`
- `nexora_customer_pilot_notification_failures_total`
- `nexora_customer_pilot_notification_retry_total`
- `nexora_customer_pilot_notification_queue_oldest_seconds`

## Events

- `CustomerPilotNotificationQueued`
- `CustomerPilotNotificationSent`
- `CustomerPilotNotificationFailed`
- `CustomerPilotNotificationRetried`
- `CustomerPilotNotificationRequeued`
