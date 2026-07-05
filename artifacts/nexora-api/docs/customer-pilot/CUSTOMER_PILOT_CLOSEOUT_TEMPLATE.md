# Customer Pilot Closeout Template

Complete this checklist at the end of the pilot window.

---

## Pilot summary

| Field | Value |
|-------|-------|
| Organization | _[Name]_ |
| Pilot window | _[Start date] – [End date]_ |
| Environment | _[Non-production tier and namespace]_ |
| Operation performed | _[Yes / No / Cancelled]_ |
| Operation type | _[e.g. scale_deployment 1→2]_ |
| Verification outcome | _[VERIFIED / VERIFICATION_FAILED / INSUFFICIENT_EVIDENCE / N/A]_ |
| Rollback performed | _[Yes / No]_ |

## Stage completion

- [ ] CONNECT — integrations validated
- [ ] VALIDATE — readiness check passed
- [ ] READ_ONLY_ASSESSMENT — assessment completed
- [ ] BASELINE_CAPTURE — baseline recorded
- [ ] PROPOSE_OPERATION — proposal recorded (if operation attempted)
- [ ] CUSTOMER_APPROVAL — approval on file (if operation attempted)
- [ ] EXECUTE — operation confirmed and run (if applicable)
- [ ] VERIFY — post-change verification completed (if applicable)
- [ ] COMPLETE — pilot closed with evidence

## Evidence retained

- [ ] Pre-operation baseline export
- [ ] Approval record with payload hash
- [ ] Execution and verification evidence
- [ ] Evidence pack export (redacted)
- [ ] Rollback evidence (if applicable)

## Safety confirmation

- [ ] No production resources accessed
- [ ] No secrets exposed in exports
- [ ] Kill switch deactivated only after closeout (if used)
- [ ] Credentials rotated per policy (if required)

## Stakeholder sign-off

| Role | Name | Date | Outcome acknowledged |
|------|------|------|----------------------|
| Customer sponsor | | | |
| Technical lead | | | |
| Approver | | | |

## Outcome statement

_Select one:_

- [ ] **Pilot successful** — one verified operation completed; evidence sufficient for closeout
- [ ] **Pilot incomplete** — insufficient evidence or blocked; no customer impact / mutation documented
- [ ] **Pilot recovered** — verification failed; rollback completed per plan

## Follow-up

| Item | Owner | Due |
|------|-------|-----|
| _[e.g. Production onboarding discussion]_ | | |
| _[e.g. Credential revocation]_ | | |

---

**Closeout completed by:** _______________________ **Date:** _______________________
