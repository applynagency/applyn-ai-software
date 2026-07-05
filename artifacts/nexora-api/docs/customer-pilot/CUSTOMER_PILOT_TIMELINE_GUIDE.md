# Customer Pilot Timeline Guide

## What's included

The unified timeline combines:

- Pilot stage transitions
- Operation proposals and status changes
- Approval packages and decisions
- Operator handoff readiness changes
- Execution and verification milestones
- Evidence availability
- Closeout requests
- Customer-safe communications and reminders

## What's excluded

Internal-only data never appears:

- Confirmation tokens, kubeconfigs, credentials
- Internal hostnames, organization IDs, scripts
- Raw provider errors
- Internal pilot history

## Using the timeline

**Customer Pilot → Timeline** shows chronological events with:

- Timestamp, type, title, description
- Status badge (proposed, awaiting approval, verified, blocked, etc.)
- Actor type: Customer admin, Platform operator, or System
- Deep link to the relevant portal page when applicable

## Filters and export

API supports filtering by status, event type, date range, and operation ID. Keyset pagination uses `next_cursor`.

Export formats: JSON, Markdown, HTML, PDF. Exports run a secret scan and block unsafe output.

## Accessibility

Timeline updates use `aria-live="polite"` regions. Status is conveyed by text labels, not color alone.
