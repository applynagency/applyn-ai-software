# Customer Pilot Email Notification Policy

## Default scope (current staging deployment)

**In-app notifications only.**

Approval reminders and pilot communications are delivered in-app; email delivery is not enabled in this deployment.

Configuration:

- `PILOT_EMAIL_NOTIFICATIONS_ENABLED=false` (default)
- `SMTP_HOST` unset

Deployment readiness treats SMTP as **not required** for GO when in-app-only mode is active.

## When email is advertised

Set `PILOT_EMAIL_NOTIFICATIONS_ENABLED=true` and configure:

- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_TLS`

Before claiming email delivery works:

1. Send one controlled internal test notification to an internal mailbox
2. Verify actual receipt
3. Record evidence in `smtp-validation.json` with `status=DELIVERED`
4. Never export recipient addresses, message bodies, or credentials in artifacts

Deployment readiness requires SMTP delivery verification when email mode is enabled.

## Customer-facing messaging

Portal and readiness outputs include:

> Approval reminders and pilot communications are delivered in-app; email delivery is not enabled in this deployment.

When email is enabled, update customer pilot documentation to describe in-app **and** email channels.

## Operator alerts (distinct from customer email)

Customer reminder email (`SMTP_HOST`) is separate from operational alert receivers:

- `PILOT_ALERT_WEBHOOK_URL` — Prometheus/Alertmanager webhook (internal only)
- `PILOT_ALERT_EMAIL` — optional internal ops mailbox

Alert delivery is **always required** for deployment GO.
