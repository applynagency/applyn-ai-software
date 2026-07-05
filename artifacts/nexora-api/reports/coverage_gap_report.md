# Coverage Gap Report

**Overall:** 77.3% (target 80%)

## Package Summary

| Package | Actual | Target | Gap |
|---------|--------|--------|-----|
| overall | 77.3% | 80% | +2.7% |
| app/agents | 77.3% (612/792) | 90% | +12.7% |
| app/services | 52.3% (1667/3190) | 90% | +37.7% |
| app/workflows | 49.2% (435/885) | 90% | +40.8% |
| app/tenancy | 61.1% (294/481) | 90% | +28.9% |

## Lowest Coverage Modules

- `app/utils/response.py` — 0.0% (10 missed / 10 statements)
- `app/utils/pagination.py` — 0.0% (7 missed / 7 statements)
- `app/tenancy/backfill.py` — 29.8% (33 missed / 47 statements)
- `app/services/organization.py` — 32.6% (122 missed / 181 statements)
- `app/auth/token_service.py` — 35.3% (22 missed / 34 statements)
- `app/workflows/execution_engine.py` — 37.3% (106 missed / 169 statements)
- `app/services/auth.py` — 38.2% (42 missed / 68 statements)
- `app/workflows/dispatcher.py` — 44.7% (282 missed / 510 statements)
- `app/workflows/engine.py` — 45.8% (32 missed / 59 statements)
- `app/services/workflow_stage.py` — 47.3% (39 missed / 74 statements)
- `app/services/deployment.py` — 47.8% (93 missed / 178 statements)
- `app/ai_agents/resolution.py` — 50.0% (19 missed / 38 statements)
- `app/services/fullstack_assembly.py` — 50.4% (67 missed / 135 statements)
- `app/services/frontend_execution.py` — 50.8% (65 missed / 132 statements)
- `app/services/workspace.py` — 50.8% (30 missed / 61 statements)
- `app/services/team_responsibility.py` — 51.2% (21 missed / 43 statements)
- `app/services/approval.py` — 51.3% (93 missed / 191 statements)
- `app/services/backend_code_review.py` — 51.4% (54 missed / 111 statements)
- `app/services/backend_architect.py` — 52.2% (55 missed / 115 statements)
- `app/services/backend_v3.py` — 52.6% (54 missed / 114 statements)
- `app/services/frontend_architect.py` — 52.6% (54 missed / 114 statements)
- `app/services/frontend_code_review.py` — 52.6% (54 missed / 114 statements)
- `app/services/frontend_v1.py` — 52.6% (54 missed / 114 statements)
- `app/services/frontend_v2.py` — 52.6% (54 missed / 114 statements)
- `app/services/frontend_v3.py` — 52.6% (54 missed / 114 statements)
