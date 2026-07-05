"""Sprint 45A — Intelligent Runbooks API.

* POST /v1/runbooks/generate   — generate a runbook for an incident class (read-only)
* GET  /v1/runbooks            — list / search runbooks
* GET  /v1/runbooks/{id}       — get a runbook
* PUT  /v1/runbooks/{id}       — manually edit a runbook (versioned)

Generation reads existing incident intelligence and never mutates incidents.
Org-scoped and audited.
"""

from fastapi import APIRouter, Query, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.runbook import (
    RunbookGenerateRequest,
    RunbookListResponse,
    RunbookResponse,
    RunbookSummary,
    RunbookUpdateRequest,
)
from app.services.runbook import RunbookService

router = APIRouter(prefix="/runbooks", tags=["Intelligent Runbooks"])


@router.post("/generate", response_model=RunbookResponse, status_code=status.HTTP_201_CREATED)
async def generate_runbook(
    data: RunbookGenerateRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await RunbookService(session).generate(current_user, org_context, data)


@router.get("", response_model=RunbookListResponse)
async def list_runbooks(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    search: str | None = Query(default=None),
    category: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    rows, total = await RunbookService(session).list(
        current_user, org_context, search=search, category=category, offset=offset, limit=limit
    )
    return RunbookListResponse(
        items=[RunbookSummary.model_validate(r) for r in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{runbook_id}", response_model=RunbookResponse)
async def get_runbook(
    runbook_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    return await RunbookService(session).get(current_user, org_context, runbook_id)


@router.put("/{runbook_id}", response_model=RunbookResponse)
async def update_runbook(
    runbook_id: str,
    data: RunbookUpdateRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await RunbookService(session).update(current_user, org_context, runbook_id, data)
