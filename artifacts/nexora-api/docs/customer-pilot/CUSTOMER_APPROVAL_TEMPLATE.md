# Customer Approval Template

Use this template when recording approval for the **single** pilot operation. Copy into your change-management system or complete via the platform approval API.

---

## Approval record

| Field | Value |
|-------|-------|
| **Approver name** | _[Full name]_ |
| **Approver email** | _[Email]_ |
| **Organization** | _[Your organization name]_ |
| **Environment** | _[e.g. staging — non-production]_ |
| **Namespace** | _[Pilot namespace]_ |
| **Cluster** | _[Cluster identifier agreed with your team]_ |
| **Operation** | _[e.g. scale_deployment: `<deployment-name>` 1 → 2 replicas]_ |
| **Exact change** | _[Resource name, namespace, replica counts, parameters]_ |
| **Rollback plan** | _[e.g. scale `<deployment-name>` 2 → 1 if verification fails]_ |
| **Expiry** | _[Date/time UTC — approval invalid after this time]_ |
| **Payload hash** | _[From platform proposal — do not modify operation after approval]_ |

## Typed confirmation (separate step)

After approval is **APPROVED**, an authorized operator must:

1. Review the proposal and preflight summary
2. Type the **exact resource name** (e.g. deployment name) in the confirmation dialog
3. Submit with the issued confirmation token

**Execution does not proceed without both approved status and matching typed confirmation.**

## Rationale (optional)

_[Why this change is acceptable in the pilot window]_

## Sign-off

- [ ] I confirm this is a **non-production** environment
- [ ] I confirm the rollback plan is adequate
- [ ] I confirm RBAC is namespace-scoped only
- [ ] I understand **one operation maximum** applies

**Approver signature / date:** _______________________

---

## Invalidation

Approval is invalidated if:

- Operation parameters change after approval (payload hash mismatch)
- Approval expires before typed confirmation
- Approver rejects the proposal

A new approval record is required before retry.
