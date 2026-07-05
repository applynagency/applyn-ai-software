# Database Drift Report

**Generated:** Emergency Recovery Sprint  
**Database:** `postgresql://nexora@db:5432/nexora`  
**Alembic head:** `024_schema_reconciliation`

## Executive summary

**No schema drift detected.** Database is aligned with Alembic head.

## Table inventory

- **59 tables** in `public` schema (including `alembic_version`)
- All expected agent run/artifact tables present through `backend_code_review`
- Tenancy tables: `organizations`, `organization_members`, `organization_invitations`

## Alembic state

| Field | Value |
|-------|-------|
| `alembic_version` exists | Yes |
| Current revision | `024_schema_reconciliation` |
| Head revision | `024_schema_reconciliation` |
| `alembic upgrade head` | No-op (success) |

## Column drift — `workspaces`

| Column | Expected | Actual |
|--------|----------|--------|
| `organization_id` | Required by ORM | Present (nullable, indexed) |
| All baseline columns | Present | Present |

**Missing columns:** none  
**Extra columns:** none

## Indexes & constraints — `workspaces`

| Name | Status |
|------|--------|
| `ix_workspaces_organization_id` | Present |
| `fk_workspaces_organization_id` | Present (ON DELETE CASCADE) |

## Historical failure (resolved)

| Error | Resolution |
|-------|------------|
| `UndefinedColumnError: workspaces.organization_id` | Migration `024_schema_reconciliation` |
| `relation "organizations" already exists` | Stamp + idempotent upgrade path |
| Missing `alembic_version` | Repaired via stamp/upgrade workflow |

## Repair recommendations

None — schema is current.

See also: [migration_repair_plan.md](./migration_repair_plan.md)  
Machine-readable: [database_drift_report.json](./database_drift_report.json)
