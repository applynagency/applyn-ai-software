# Tamper-Evident Audit Logging

Audit events are **append-only**, scoped to an organization, and chained with a
per-organization SHA-256 **hash chain**. Any modification, deletion, or
reordering of stored entries is detectable through integrity verification.

## Data model (`app/models/audit.py`)

`audit_logs` columns added by this upgrade:

| Column | Purpose |
| --- | --- |
| `organization_id` | Tenant scope (FK `organizations.id`, `ON DELETE SET NULL`). `NULL` = system/global chain. |
| `sequence` | Monotonic position within the organization's chain (`0` = genesis). |
| `entry_hash` | SHA-256 hex of the entry's canonical content (includes `prev_hash`). |
| `prev_hash` | `entry_hash` of the previous entry in the same chain (`NULL` for genesis). |

Existing columns: `id`, `created_at`, `updated_at`, `user_id`, `action`,
`resource_type`, `resource_id`, `details`, `ip_address`, `user_agent`, `status`.

### Immutability

ORM `UPDATE` and `DELETE` on an `AuditLog` raise `AuditImmutableError`
(`before_update` / `before_delete` mapper events). The application never mutates
an audit row after creation. The **only** sanctioned deletion path is retention
purge, which uses a core bulk delete.

## Hash chain (`app/services/audit/hashing.py`)

For each entry a canonical JSON string is built over its immutable fields
(`id`, `organization_id`, `sequence`, `user_id`, `action`, `resource_type`,
`resource_id`, `details`, `ip_address`, `user_agent`, `status`, `created_at`,
`prev_hash`) with sorted keys, and `entry_hash = sha256(canonical)`.

Because `prev_hash` is part of the hashed content, each entry transitively
commits to the entire preceding chain:

```
entry[n].prev_hash == entry[n-1].entry_hash
entry[n].entry_hash == sha256(canonical(entry[n]))   # canonical includes prev_hash
```

Chains are **per organization** (independent genesis per org); `NULL`-org events
form their own system chain.

## Writer (`AuditLogRepository.log`)

All audit rows funnel through `AuditLogRepository.log(...)` →
`BaseRepository.create`'s replacement chain logic. The writer:

1. Resolves `organization_id` (explicit arg, else `details['organization_id']` —
   so existing callers that carry the org inside `details` are chained without
   code changes).
2. Reads the last entry of that chain to derive `sequence` and `prev_hash`.
3. Stamps `id` + `created_at`, computes `entry_hash`, and inserts.

> Concurrency note: the chain is derived from the latest committed/flushed entry
> visible to the writing session. Audit writes within a request are serialized
> per session, so chains are correct in normal operation. Under heavy concurrent
> writes to the *same* organization across replicas, integrity verification will
> surface any anomaly rather than silently corrupting data.

## API (`/v1/audit`)

Reads are organization-scoped (the caller's current org from the access token)
and restricted to organization **OWNER/ADMIN** (or superusers). Retention purge
is **superuser-only**.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/v1/audit/logs` | Filtered, paginated listing (newest first). |
| `GET` | `/v1/audit/logs/export?format=csv\|json` | Export filtered entries (oldest first). |
| `GET` | `/v1/audit/verify` | Verify the organization's chain integrity. |
| `POST` | `/v1/audit/retention/purge` | Delete entries older than the retention window. |

### Filtering

`action`, `resource_type`, `resource_id`, `user_id`, `status`, `start`, `end`
(ISO-8601 instants), `offset`, `limit` (≤ 500).

### Export

`format=json` returns a JSON array; `format=csv` returns `text/csv`. Both send a
`Content-Disposition: attachment` header and are bounded by
`AUDIT_EXPORT_MAX_ROWS`. CSV serializes `details` as a JSON string.

### Integrity verification response

```json
{
  "organization_id": "…",
  "total": 1240,
  "verified": 1240,
  "legacy_unhashed": 0,
  "valid": true,
  "errors": [],
  "first_sequence": 0,
  "last_sequence": 1239
}
```

`errors[]` entries are `{ "id", "sequence", "error" }` where `error` is:

- `hash_mismatch` — a stored field was changed (content tampering).
- `broken_link` — an entry's `prev_hash` no longer matches the previous entry
  (deletion, insertion, or reordering).

Entries written before this upgrade (no `entry_hash`) are reported as
`legacy_unhashed` and skipped.

## Retention (`app/services/audit/service.py`)

`AUDIT_RETENTION_DAYS` (default `0` = keep forever) controls the retention
window. `purge_expired(...)` deletes entries older than the cutoff. Purge removes
a contiguous oldest prefix, so the remaining entries stay internally linked and
verifiable (the new oldest entry's `prev_hash` simply points at a purged
predecessor and is treated as a boundary).

## Configuration (`app/core/config.py`)

| Setting | Default | Meaning |
| --- | --- | --- |
| `AUDIT_RETENTION_DAYS` | `0` | Retention window in days; `0` = retain indefinitely. |
| `AUDIT_EXPORT_MAX_ROWS` | `50000` | Max rows returned by a single export. |

## Migration

`alembic/versions/0005_audit.py` adds the new columns + indexes, inspector-guarded
for idempotency (a fresh `upgrade head` already has them via the squashed
baseline; a previously-stamped database gets them added). Alembic HEAD =
`0005_audit`.

## Tests (`app/tests/test_audit.py`)

Covers the hash chain (sequence + linkage), per-organization chains, org-scoped
listing + filtering, CSV/JSON export, integrity verification (valid chain,
content-tamper detection, deletion/broken-link detection), retention purge,
ORM-level immutability (update + delete blocked), and access control
(non-admin role forbidden).
