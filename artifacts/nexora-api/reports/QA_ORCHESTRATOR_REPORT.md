# QA Orchestrator Report — Sprint 29A.3

**Date:** 2026-06-17  
**Scope:** Lifecycle orchestrator auto-resolution of QA chain before Assembly

---

## Summary

Deploy, Release, Regeneration, and Assembly customer paths now **automatically resolve the full QA chain** before Assembly. Customers never need to manually invoke QA agents.

---

## MASTER_BUILD_CHAIN Update

**File:** `app/lifecycle/prerequisites.py`

```
FOUNDATION → BACKEND → FRONTEND → QA_AGENT_CHAIN → FINALIZATION
```

`QA_AGENT_CHAIN` (from `app/lifecycle/impact.py`):

1. `qa_architect`
2. `unit_test_generator`
3. `integration_test`
4. `security_test`
5. `performance_test`
6. `qa_approval`

`DEPLOY_READINESS_CHAIN` = `MASTER_BUILD_CHAIN[:-1]` — now includes entire QA chain through approval.

---

## AgentPrerequisiteChecker

Added satisfaction checks for all six QA agents:

| Agent | Satisfied when |
|-------|----------------|
| `qa_architect` … `performance_test` | Completed run with artifacts |
| `qa_approval` | Completed run with `QA_APPROVED` or `QA_APPROVED_WITH_WARNINGS` |

`has_approved_qa_approval()` — shared with assembly gate.

---

## LifecycleOrchestratorService

**File:** `app/lifecycle/orchestrator.py`

| Method | QA behavior |
|--------|-------------|
| `ensure_assembly_prerequisites` | Runs chain **excluding** `fullstack_assembly`; enforces QA gate after chain |
| `ensure_deploy_prerequisites` | Inherits QA via `DEPLOY_READINESS_CHAIN` |
| `regenerate_version` | `prerequisites_for_agents()` now includes `QA_AGENT_CHAIN` for finalization targets |
| `create_release` | Uses `regenerate_version` → QA auto-resolved |
| `_run_agent_chain` | After `qa_approval` dispatch, calls `_ensure_qa_approval_gate()` |

Customer errors from QA gate use `translate_customer_error()` → **"Finishing validation checks."**

---

## Impact Analysis

**File:** `app/lifecycle/impact.py`

Regeneration impact now includes `QA_AGENT_CHAIN` for all scopes (frontend-only, backend-only, full).

---

## Tests

| File | Tests |
|------|-------|
| `test_lifecycle_orchestrator_qa.py` | Chain includes QA; orchestrator dispatches QA agents; deploy includes QA |
| `test_lifecycle_orchestrator.py` | Updated chain prefix and prerequisite expectations |
| `test_qa_chain_e2e.py` | Deploy readiness chain includes QA agents |

---

## Customer Journey

| Action | QA chain auto-resolved |
|--------|------------------------|
| Deploy | ✅ |
| Release | ✅ |
| Regeneration | ✅ |
| Assembly (API) | ✅ via `ensure_assembly_prerequisites` |

Customers do not see internal agent names; progress messages remain customer-safe.
