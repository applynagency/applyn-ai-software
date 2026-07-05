# Test Failure Matrix (Emergency Recovery)

## Summary

| Metric | Pre-recovery | Post-recovery |
|--------|--------------|---------------|
| **Total tests** | 2530 (109 failed) | **2550 passed** |
| **Collection errors** | 2 (syntax in stale Docker image) | 0 |
| **Failed** | 109 | 0 |
| **Skipped** | 0 | 0 |
| **Errors** | 0 | 0 |

## Root cause analysis

| Category | Count (pre) | Root cause | Fix |
|----------|-------------|------------|-----|
| **Docker image drift** | 2 collection + 109 failures | `docker compose run` used image built from stale code; test files had invalid import syntax in image | `docker compose build api`; mount `-v $(pwd):/app` for dev runs |
| **workflow** | ~15 | Stale image / broken conftest imports | Rebuild image |
| **approval** | ~12 | Same | Rebuild image |
| **deployment** | ~8 | Same | Rebuild image |
| **backend architect** | ~6 | Same | Rebuild image |
| **backend v1** | ~8 | Same | Rebuild image |
| **backend v2** | ~8 | Same | Rebuild image |
| **backend v3** | ~10 | Same | Rebuild image |
| **backend code review** | ~8 | Same | Rebuild image |
| **team mappings** | ~6 | Same | Rebuild image |
| **dispatcher** | ~5 | Same | Rebuild image |
| **regression** | ~21 | Same | Rebuild image |

## Category breakdown (pre-recovery failures)

Failures were **not** independent logic bugs across 109 tests. They clustered because:

1. Stale Docker image contained broken `test_approval_execution.py` and `test_fullstack_assembly_execution.py` imports (`SyntaxError` on line 1).
2. When collection partially succeeded in older runs, downstream workflow/team-mapping assertions failed against outdated mappings in the image.

## Post-recovery additions

| File | Purpose |
|------|---------|
| `app/tests/test_internal_agents_direct.py` | 20 direct agent tests (mocked LLM) for implementation coverage |

## Verification command

```bash
docker compose build api
docker compose run --rm --no-deps --user root -v "$(pwd):/app" \
  -e ENVIRONMENT=test -e JWT_SECRET_KEY=test-secret-key-for-verification-only \
  api bash -c 'pip install -q -r requirements-dev.txt && pytest app/tests -q'
```

**Result:** 2550 passed
