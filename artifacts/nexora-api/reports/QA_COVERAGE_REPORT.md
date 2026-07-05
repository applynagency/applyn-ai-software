# QA Chain Coverage Report

**Audit date:** 2026-06-17  
**Scope:** Test coverage across all six QA agents  
**Test runner:** pytest 9.1.0 (Docker, Python 3.11.15)

---

## Overview

| Metric | Value |
|--------|-------|
| QA-dedicated test files | 66 |
| QA-dedicated test functions | 318 |
| Full QA suite (incl. dispatcher parametrization) | 551 tests |
| Pass rate | 549/551 (99.6%) |
| Sprint 29A.1 target | 100+ tests |
| Sprint 29A.2 target | 150+ additional tests |
| Combined QA test count | 318 dedicated + 233 dispatcher parametrization overlap ≈ **551 executed** |

---

## Per-Agent Test Counts

| Agent | Test Files | Test Functions | Categories Covered |
|-------|:----------:|:--------------:|-------------------|
| QA Architect | 11 | 59 | API, validator, schema, markdown, prompt, audit, permissions, tenancy, dispatcher, team mapping, extended |
| Unit Test Generator | 11 | 51 | API, validator, schema, markdown, prompt, audit, permissions, tenancy, dispatcher, team mapping, extended |
| Integration Test | 11 | 50 | API, validator, schema, markdown, prompt, audit, permissions, tenancy, dispatcher, team mapping, extended |
| Security Test | 11 | 51 | API, validator, schema, markdown, prompt, audit, permissions, tenancy, dispatcher, team mapping, extended |
| Performance Test | 11 | 50 | API, validator, schema, markdown, prompt, audit, permissions, tenancy, dispatcher, team mapping, extended |
| QA Approval | 11 | 57 | API, validator, schema, markdown, prompt, audit, permissions, tenancy, dispatcher, team mapping, extended |
| **Total** | **66** | **318** | |

---

## Coverage Dimensions

### API Layer

Each agent has a primary API test file (`test_<agent>.py` or `test_qa_architect.py`) covering:

- POST `/run` success (201, COMPLETED status, artifact)
- Prerequisite rejection (422)
- GET `/runs/{id}`
- GET `/artifacts/{id}`
- GET `/{requirement_id}` list

**Coverage:** ✅ Complete for all six agents

### Validator Layer

| Agent | Test File | Test Functions | MINIMUM_COUNTS Tested |
|-------|-----------|:--------------:|----------------------|
| QA Architect | `test_qa_architect_validator.py` | 16 | ✅ |
| Unit Test Generator | `test_unit_test_validator.py` | 12 | ✅ |
| Integration Test | `test_integration_test_validator.py` | 11 | ✅ |
| Security Test | `test_security_test_validator.py` | 10 | ✅ |
| Performance Test | `test_performance_test_validator.py` | 10 | ✅ |
| QA Approval | `test_qa_approval_validator.py` | 19 | ✅ |

**Total validator tests:** 78

### Schema Layer

| Agent | Test File | Test Functions |
|-------|-----------|:--------------:|
| QA Architect | `test_qa_architect_schema.py` | 8 |
| Unit Test Generator | `test_unit_test_schema.py` | 8 |
| Integration Test | `test_integration_test_schema.py` | 7 |
| Security Test | `test_security_test_schema.py` | 7 |
| Performance Test | `test_performance_test_schema.py` | 7 |
| QA Approval | `test_qa_approval_schema.py` | 7 |

**Total schema tests:** 44

### Markdown Export

| Agent | Test File | Test Functions |
|-------|-----------|:--------------:|
| QA Architect | `test_qa_architect_markdown.py` | 5 |
| Unit Test Generator | `test_unit_test_markdown.py` | 5 |
| Integration Test | `test_integration_test_markdown.py` | 5 |
| Security Test | `test_security_test_markdown.py` | 7 |
| Performance Test | `test_performance_test_markdown.py` | 6 |
| QA Approval | `test_qa_approval_markdown.py` | 4 |

**Total markdown tests:** 32

### Prompt Builder

| Agent | Test File | Test Functions |
|-------|-----------|:--------------:|
| QA Architect | `test_qa_architect_prompt.py` | 4 |
| Unit Test Generator | `test_unit_test_prompt.py` | 4 |
| Integration Test | `test_integration_test_prompt.py` | 4 |
| Security Test | `test_security_test_prompt.py` | 4 |
| Performance Test | `test_performance_test_prompt.py` | 4 |
| QA Approval | `test_qa_approval_prompt.py` | 4 |

**Total prompt tests:** 24

### Audit Events

| Agent | Test File | Events Verified |
|-------|-----------|-----------------|
| QA Architect | `test_qa_architect_audit.py` | `qa_architect_started` |
| Unit Test Generator | `test_unit_test_audit.py` | `unit_test_started` |
| Integration Test | `test_integration_test_audit.py` | `integration_test_started` |
| Security Test | `test_security_test_audit.py` | `security_test_started` |
| Performance Test | `test_performance_test_audit.py` | `performance_test_started` |
| QA Approval | `test_qa_approval_audit.py` | `qa_approval_started`, `qa_approved`/`qa_rejected` |

**Total audit tests:** 18 (3 per agent average)

### Permissions

| Agent | Test File | Test Functions | Scenarios |
|-------|-----------|:--------------:|-----------|
| QA Architect | `test_qa_architect_permissions.py` | 4 | Owner write, viewer read-only, cross-org denied |
| Unit Test Generator | `test_unit_test_permissions.py` | 3 | Same pattern |
| Integration Test | `test_integration_test_permissions.py` | 4 | Same pattern |
| Security Test | `test_security_test_permissions.py` | 4 | Same pattern |
| Performance Test | `test_performance_test_permissions.py` | 4 | Same pattern |
| QA Approval | `test_qa_approval_permissions.py` | 4 | Same pattern |

**Total permission tests:** 23

### Tenancy Isolation

| Agent | Test File | Test Functions |
|-------|-----------|:--------------:|
| QA Architect | `test_qa_architect_tenancy.py` | 2 |
| Unit Test Generator | `test_unit_test_tenancy.py` | 2 |
| Integration Test | `test_integration_test_tenancy.py` | 2 |
| Security Test | `test_security_test_tenancy.py` | 2 |
| Performance Test | `test_performance_test_tenancy.py` | 2 |
| QA Approval | `test_qa_approval_tenancy.py` | 2 |

**Total tenancy tests:** 12

### Dispatcher Integration

| Agent | Test File | Test Functions |
|-------|-----------|:--------------:|
| QA Architect | `test_qa_architect_dispatcher.py` | 3 |
| Unit Test Generator | `test_unit_test_dispatcher.py` | 3 |
| Integration Test | `test_integration_test_dispatcher.py` | 3 |
| Security Test | `test_security_test_dispatcher.py` | 3 |
| Performance Test | `test_performance_test_dispatcher.py` | 3 |
| QA Approval | `test_qa_approval_dispatcher.py` | 3 |

Plus shared: `test_dispatcher_all_agents_sprint.py` (parametrized all agents)

**Total dispatcher tests:** 18 dedicated + 24 parametrized (all agents)

### Team Mapping

| Agent | Test File | Status |
|-------|-----------|--------|
| QA Architect | `test_qa_architect_team_mapping.py` | ⚠️ 1/2 fail (stale QA team assertion) |
| Unit Test Generator | `test_unit_test_team_mapping.py` | ⚠️ 1/2 fail (stale QA team assertion) |
| Integration Test | `test_integration_test_team_mapping.py` | ✅ |
| Security Test | `test_security_test_team_mapping.py` | ✅ |
| Performance Test | `test_performance_test_team_mapping.py` | ✅ |
| QA Approval | `test_qa_approval_team_mapping.py` | ✅ |

PRODUCT team mapping tests (membership in `EXPECTED_PRODUCT_TEAM_AGENTS`) pass for all agents.

### Extended / Edge Cases

| Agent | Test File | Test Functions |
|-------|-----------|:--------------:|
| QA Architect | `test_qa_architect_extended.py` | 4 |
| Unit Test Generator | `test_unit_test_extended.py` | 4 |
| Integration Test | `test_integration_test_extended.py` | 4 |
| Security Test | `test_security_test_extended.py` | 4 |
| Performance Test | `test_performance_test_extended.py` | 4 |
| QA Approval | `test_qa_approval_extended.py` | 4 |

**Total extended tests:** 24

---

## Coverage Matrix

| Dimension | QA Architect | Unit Tests | Integration | Security | Performance | QA Approval |
|-----------|:---:|:---:|:---:|:---:|:---:|:---:|
| API | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Validator | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Schema | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Markdown | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Prompt | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Audit | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Permissions | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Tenancy | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Dispatcher | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Team Mapping | ⚠️ | ⚠️ | ✅ | ✅ | ✅ | ✅ |
| Extended | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## Coverage Gaps

| Gap | Severity | Description |
|-----|----------|-------------|
| Stale QA team mapping tests | Medium | 2 tests assert pre-29A.2 two-agent QA team |
| No unified E2E chain test | High | No single test: BE → QA chain → Assembly |
| No live LLM integration test | Medium | All agent runs use mocked outputs |
| Assembly QA prerequisite | High | No test asserts assembly rejects missing QA Approval |
| Lifecycle orchestrator QA | Medium | No tests for customer auto-resolution through QA chain |
| UI tests | Medium | No automated browser/E2E tests for `/qa-*` routes |

---

## Sprint Target Compliance

| Sprint | Target | Actual | Status |
|--------|--------|--------|--------|
| 29A.1 | 100+ tests (QA Architect + Unit Test Generator) | 110 dedicated | ✅ |
| 29A.2 | 150+ tests (4 advanced agents) | 208 dedicated | ✅ |
| Combined | 250+ QA tests | 318 dedicated, 551 in full suite | ✅ |

---

## Coverage Verdict

| Category | Assessment |
|----------|------------|
| Per-agent unit/integration coverage | **Strong** — all 11 dimensions per agent |
| Cross-agent chain coverage | **Partial** — pipeline helpers exist; no assembly gate test |
| Production E2E coverage | **Weak** — mocked agents only |
| Test suite health | **99.6%** pass rate (2 stale tests) |

### Is test coverage sufficient for production?

**Per-agent coverage: YES**  
**End-to-end QA gate coverage: NO**
