"""Audit log API — filtered listing, CSV/JSON export, integrity verification,
retention purge.

Reads are organization-scoped (the caller's current organization) and restricted
to organization OWNER/ADMIN (or superusers). Retention purge is superuser-only.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, Response

from app.auth.dependencies import CurrentSuperuser, DBSession
from app.auth.org_context import OrgContext, OrgContextDep
from app.core.config import settings
from app.models.organization import OrganizationRole
from app.repositories.audit import AuditLogRepository
from app.schemas.audit import (
    AuditIntegrityResponse,
    AuditLogListResponse,
    AuditLogResponse,
    AuditRetentionResponse,
)
from app.services.audit.service import parse_instant, purge_expired, verify_chain

router = APIRouter(prefix="/audit", tags=["Audit"])

_EXPORT_COLUMNS = [
    "id",
    "sequence",
    "organization_id",
    "created_at",
    "user_id",
    "action",
    "resource_type",
    "resource_id",
    "status",
    "ip_address",
    "user_agent",
    "entry_hash",
    "prev_hash",
    "details",
]


async def require_audit_reader(org: OrgContextDep) -> OrgContext:
    _ = org.requires_organization  # raises 403 if no organization in context
    if not (org.user.is_superuser or org.role in (OrganizationRole.OWNER, OrganizationRole.ADMIN)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Audit access requires organization OWNER or ADMIN",
        )
    return org


AuditReader = Annotated[OrgContext, Depends(require_audit_reader)]


def _row_dict(row) -> dict:
    return AuditLogResponse.model_validate(row).model_dump(mode="json")


@router.get("/logs", response_model=AuditLogListResponse)
async def list_logs(
    reader: AuditReader,
    session: DBSession,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    user_id: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    start: str | None = None,
    end: str | None = None,
    offset: int = 0,
    limit: int = Query(50, ge=1, le=500),
):
    repo = AuditLogRepository(session)
    rows, total = await repo.list_filtered(
        reader.organization_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        status=status_filter,
        start=parse_instant(start),
        end=parse_instant(end),
        offset=offset,
        limit=limit,
    )
    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(r) for r in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/logs/export")
async def export_logs(
    reader: AuditReader,
    session: DBSession,
    format: str = Query("json", pattern="^(json|csv)$"),
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    user_id: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    start: str | None = None,
    end: str | None = None,
):
    repo = AuditLogRepository(session)
    rows, _ = await repo.list_filtered(
        reader.organization_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        status=status_filter,
        start=parse_instant(start),
        end=parse_instant(end),
        offset=0,
        limit=settings.AUDIT_EXPORT_MAX_ROWS,
        ascending=True,
    )

    if format == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=_EXPORT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            record = _row_dict(r)
            record["details"] = json.dumps(record.get("details")) if record.get("details") else ""
            writer.writerow(record)
        return Response(
            content=buffer.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit-logs.csv"},
        )

    return JSONResponse(
        content=[_row_dict(r) for r in rows],
        headers={"Content-Disposition": "attachment; filename=audit-logs.json"},
    )


@router.get("/verify", response_model=AuditIntegrityResponse)
async def verify(reader: AuditReader, session: DBSession):
    result = await verify_chain(session, reader.organization_id)
    return AuditIntegrityResponse(**result)


@router.post("/retention/purge", response_model=AuditRetentionResponse)
async def retention_purge(
    current_user: CurrentSuperuser,
    session: DBSession,
    days: int | None = Query(None, ge=1),
    organization_id: str | None = None,
):
    retention_days = days if days is not None else settings.AUDIT_RETENTION_DAYS
    result = await purge_expired(
        session, retention_days=retention_days, organization_id=organization_id
    )
    return AuditRetentionResponse(**result)
