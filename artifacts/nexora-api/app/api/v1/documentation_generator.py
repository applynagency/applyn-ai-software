"""Sprint 51E - Customer Documentation Portal generator API.

* POST /v1/docs/generate  - scan routes/navigation/modules and generate guides
* GET  /v1/docs/portal    - the Customer Documentation Portal (guides + navigation)
* GET  /v1/docs/manual    - export a PDF/HTML/Markdown manual (?guide=&format=)

Builds on the Sprint 51A Documentation Center. Org-scoped, audited, role-gated.
Strictly additive.
"""

from fastapi import APIRouter, Query, Response, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.documentation_generator import GenerateResponse, PortalResponse
from app.services.documentation_generator import DocumentationGeneratorService

router = APIRouter(prefix="/docs", tags=["Documentation"])


@router.post("/generate", response_model=GenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate_documentation(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await DocumentationGeneratorService(session).generate(current_user, org_context)


@router.get("/portal", response_model=PortalResponse)
async def get_portal(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await DocumentationGeneratorService(session).portal(current_user, org_context)


@router.get("/manual")
async def export_manual(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    guide: str = Query(default="all"),
    format: str = Query(default="pdf"),
):
    content, media_type, filename = await DocumentationGeneratorService(session).manual(
        current_user, org_context, guide=guide, fmt=format
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
