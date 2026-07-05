"""Canonical serialization and hash-chain computation for audit entries.

The exact same canonical form is used when writing an entry and when verifying
it, so any later modification of a stored field changes the recomputed hash and
is detected. ``prev_hash`` is part of the canonical content, so each entry's hash
transitively commits to the entire preceding chain.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.isoformat() + "+00:00"
    return value.isoformat()


def canonical_payload(
    *,
    id: str,
    organization_id: str | None,
    sequence: int | None,
    user_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    details: dict | None,
    ip_address: str | None,
    user_agent: str | None,
    status: str,
    created_at: datetime | None,
    prev_hash: str | None,
) -> str:
    """Deterministic JSON string over the entry's immutable fields."""
    payload = {
        "id": id,
        "organization_id": organization_id,
        "sequence": sequence,
        "user_id": user_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "status": status,
        "created_at": _iso(created_at),
        "prev_hash": prev_hash,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_entry_hash(canonical: str) -> str:
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def row_canonical(row) -> str:
    """Canonical form for a persisted ``AuditLog`` instance."""
    return canonical_payload(
        id=row.id,
        organization_id=row.organization_id,
        sequence=row.sequence,
        user_id=row.user_id,
        action=row.action,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        details=row.details,
        ip_address=row.ip_address,
        user_agent=row.user_agent,
        status=row.status,
        created_at=row.created_at,
        prev_hash=row.prev_hash,
    )


def row_hash(row) -> str:
    return compute_entry_hash(row_canonical(row))
