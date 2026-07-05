# Approval Reminders Guide

## When reminders are sent

For **PENDING** approvals only:

| Reminder | Timing |
|----------|--------|
| 24-hour | When expiry is 23–24 hours away |
| 1-hour | When expiry is within 1 hour |
| Expired | After approval expiry |

## What reminders never do

- Auto-approve or extend approvals
- Recreate or modify approval packages
- Advance pilot stages
- Trigger execution

## Deduplication

Each approval receives at most one reminder per type (`24H`, `1H`, `EXPIRED`), tracked in `pilot_approval_reminder_deliveries`.

## Preferences

Disable approval reminders in **Customer Pilot → Preferences**. Expired approvals still appear in the timeline for audit visibility.

## After expiry

A new approval package and customer decision are required before an operator can proceed to typed confirmation.
