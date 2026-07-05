"""Sprint 44A — Postmortem API.

* GET  /v1/postmortems                          — list postmortems (paginated)
* GET  /v1/postmortems/{id}                      — get a postmortem
* GET  /v1/postmortems/{id}/export              — export (pdf | html | markdown)
* POST /v1/incidents/{id}/generate-postmortem   — generate / regenerate

Generating or exporting never modifies the incident workflow. Org-scoped and
audited.
"""

from fastapi import APIRouter, Query, Response, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.postmortem import (
    GeneratePostmortemRequest,
    PostmortemListResponse,
    PostmortemResponse,
    PostmortemSummary,
    PostmortemUpdateRequest,
)
from app.services.postmortem import PostmortemService

router = APIRouter(tags=["Postmortems"])


@router.get("/postmortems", response_model=PostmortemListResponse)
async def list_postmortems(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    rows, total = await PostmortemService(session).list(
        current_user, org_context, offset=offset, limit=limit
    )
    return PostmortemListResponse(
        items=[PostmortemSummary.model_validate(r) for r in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/postmortems/{postmortem_id}", response_model=PostmortemResponse)
async def get_postmortem(
    postmortem_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    return await PostmortemService(session).get(current_user, org_context, postmortem_id)


@router.patch("/postmortems/{postmortem_id}", response_model=PostmortemResponse)
async def update_postmortem(
    postmortem_id: str,
    data: PostmortemUpdateRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await PostmortemService(session).update(
        current_user, org_context, postmortem_id, data
    )


@router.get("/postmortems/{postmortem_id}/export")
async def export_postmortem(
    postmortem_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    format: str = Query(default="pdf"),
):
    content, media_type, filename = await PostmortemService(session).export(
        current_user, org_context, postmortem_id, format
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/incidents/{investigation_id}/generate-postmortem",
    response_model=PostmortemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_postmortem(
    investigation_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    data: GeneratePostmortemRequest | None = None,
):
    force = data.force if data is not None else True
    return await PostmortemService(session).generate(
        current_user, org_context, investigation_id, force=force
    )
