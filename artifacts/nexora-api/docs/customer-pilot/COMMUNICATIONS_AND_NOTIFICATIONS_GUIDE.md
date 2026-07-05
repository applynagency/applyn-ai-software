# Communications and Notifications Guide

## What you'll receive

Customer admins receive **in-app notifications** for:

- Pilot readiness changes
- Approval requests and reminders (24h and 1h before expiry)
- Approval expiry
- Operator status updates
- Verification and evidence availability
- Closeout updates

**Email delivery:** Approval reminders and pilot communications are delivered in-app in the current deployment. Email is available only when your operator has enabled SMTP (`PILOT_EMAIL_NOTIFICATIONS_ENABLED`); until then, use in-app notifications and the portal timeline.

## Notification preferences

Open **Customer Pilot → Preferences** to configure:

- In-app notifications
- Email (when available)
- Approval reminders (default: on)
- Evidence-ready alerts
- Closeout notifications
- Preferred timezone for display

Disabling a channel stops delivery but **does not** remove events from the portal timeline.

## Communications center

**Customer Pilot → Communications** lists platform messages. You can:

- Read customer-safe updates
- Acknowledge receipt
- Add plain-text comments (rate limited; no HTML/markdown)

You cannot edit operator messages or send operational commands.

## Status labels

Messages and timeline events use clear statuses:

- Proposed → Awaiting customer approval → Customer approved
- Awaiting platform operator confirmation → Executing
- Verification pending → Verified / Verification failed / Blocked
- Closeout pending → Closed
