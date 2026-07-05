"""Audit chain integrity verification and retention purge."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base import utcnow
from app.models.audit import AuditLog
from app.repositories.audit import AuditLogRepository
from app.services.audit.hashing import row_hash

logger = structlog.get_logger(__name__)


async def verify_chain(session: AsyncSession, organization_id: str | None) -> dict:
    """Recompute and validate the hash chain for an organization.

    Detects content tampering (a stored field changed → hash mismatch) and
    structural tampering (deletion / insertion / reordering → broken link).
    Entries written before the tamper-evident upgrade (no ``entry_hash``) are
    reported as ``legacy_unhashed`` and skipped.
    """
    repo = AuditLogRepository(session)
    rows = await repo.list_chain(organization_id)

    errors: list[dict] = []
    verified = 0
    legacy = 0
    prev: AuditLog | None = None

    for row in rows:
        if not row.entry_hash:
            legacy += 1
            prev = None  # legacy rows break linkage continuity
            continue

        expected = row_hash(row)
        if expected != row.entry_hash:
            errors.append(
                {"id": row.id, "sequence": row.sequence, "error": "hash_mismatch"}
            )
        if prev is not None and row.prev_hash != prev.entry_hash:
            errors.append(
                {"id": row.id, "sequence": row.sequence, "error": "broken_link"}
            )
        verified += 1
        prev = row

    hashed = [r for r in rows if r.entry_hash]
    return {
        "organization_id": organization_id,
        "total": len(rows),
        "verified": verified,
        "legacy_unhashed": legacy,
        "valid": not errors,
        "errors": errors,
        "first_sequence": hashed[0].sequence if hashed else None,
        "last_sequence": hashed[-1].sequence if hashed else None,
    }


async def purge_expired(
    session: AsyncSession,
    *,
    retention_days: int,
    organization_id: str | None = None,
) -> dict:
    """Delete audit entries older than ``retention_days``.

    This is the only sanctioned deletion path; it uses a core bulk delete (the
    ORM-level immutability guard intentionally does not apply here). Purging
    removes a contiguous oldest prefix, so the remaining entries stay internally
    linked and verifiable.
    """
    if retention_days <= 0:
        return {"deleted": 0, "retention_days": retention_days, "cutoff": None}

    cutoff = utcnow() - timedelta(days=retention_days)

    # Select candidates and compare in Python so the cutoff works identically on
    # PostgreSQL (tz-aware columns) and SQLite (naive datetimes from the driver).
    select_stmt = select(AuditLog.id, AuditLog.created_at)
    if organization_id is not None:
        select_stmt = select_stmt.where(AuditLog.organization_id == organization_id)
    candidates = await session.execute(select_stmt)

    expired_ids = [
        row_id
        for row_id, created in candidates
        if created is not None
        and (created if created.tzinfo else created.replace(tzinfo=UTC)) < cutoff
    ]

    deleted = 0
    if expired_ids:
        result = await session.execute(
            delete(AuditLog)
            .where(AuditLog.id.in_(expired_ids))
            .execution_options(synchronize_session=False)
        )
        deleted = result.rowcount or len(expired_ids)
    logger.info(
        "audit_retention_purge",
        deleted=deleted,
        retention_days=retention_days,
        organization_id=organization_id,
        cutoff=cutoff.isoformat(),
    )
    return {
        "deleted": deleted,
        "retention_days": retention_days,
        "cutoff": cutoff,
    }


def parse_instant(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
