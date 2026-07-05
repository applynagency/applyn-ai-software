# Customer Pilot Portal Guide

Welcome to the Customer Pilot portal. This area helps your organization review, approve, and track a **scoped non-production pilot** with Nexora.

## Who can use this portal?

- **View access:** organization members with read permissions
- **Approve operations and request closeout:** customer administrators (organization owners/admins)

The portal appears when your organization has an active pilot enrollment or when an admin is eligible to begin onboarding and readiness review.

## What you can do

1. **Review pilot scope** — see your non-production environment, namespace, and safety limits (operation count, cooldown, kill switch).
2. **Check integration readiness** — badges show whether Kubernetes, source control, and observability connections are fresh and healthy.
3. **Review proposed operations** — read the exact change, rollback plan, and risk summary before deciding.
4. **Approve or reject** — record a named decision with rationale. Approval does **not** execute the change.
5. **Track execution and verification** — see when a platform operator confirms and runs the operation, and whether verification passed.
6. **View evidence** — redacted before/after state, audit timeline, and export packs (JSON, Markdown, HTML, PDF).
7. **Request closeout** — ask Nexora to review and close the pilot when prerequisites are met.

## What you cannot do

- Execute, confirm, roll back, or cancel operations from this portal
- Access another organization's data
- Run operations in production environments
- Automatically close the pilot (operator review is required)

## Navigation

| Page | Purpose |
|------|---------|
| Overview | Scope, timeline, safety settings, current status |
| Readiness | Integration and launch readiness |
| Operation | Proposed change details |
| Approval | Immutable approval package and decision form |
| Execution | Status after approval (operator confirmation separate) |
| Evidence | Verification results and exports |
| Closeout | Request formal pilot closure |

## Notifications

You receive in-app notifications for readiness changes, approval deadlines, execution milestones, evidence availability, and closeout updates. Links open directly to the relevant portal page.

## Need help?

Contact your Nexora platform operator for execution questions. For integration setup, use **Customer Onboarding** first, then return here when readiness is **GO**.
