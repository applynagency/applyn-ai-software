"""Sprint 56A.1 — Documentation Readiness Report.

Exposes ``GET /v1/docs/readiness`` returning a platform-wide documentation
readiness snapshot (documentation score, screenshot coverage, modules/journeys/
integrations ready, and an overall release-ready flag). Read-only, org-scoped.
"""

from fastapi import APIRouter

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.customer_success import (
    ImageRenderingRepairResult,
    ImageRenderingReport,
    ReadinessReport,
    ScreenshotAuditReport,
    VerificationReadinessReport,
    VisualReadinessReport,
)
from app.services.customer_success import CustomerSuccessService
from app.services.documentation_image_verification import (
    DocumentationImageVerificationEngine,
)

router = APIRouter(prefix="/docs", tags=["Documentation"])


@router.get("/readiness", response_model=ReadinessReport)
async def get_docs_readiness(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return CustomerSuccessService().readiness()


@router.get("/visual-readiness", response_model=VisualReadinessReport)
async def get_docs_visual_readiness(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return CustomerSuccessService().visual_readiness()


@router.get("/verification-readiness", response_model=VerificationReadinessReport)
async def get_docs_verification_readiness(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return CustomerSuccessService().verification_readiness()


@router.get("/screenshot-audit", response_model=ScreenshotAuditReport)
async def get_docs_screenshot_audit(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """Sprint 56F.7 — audit every generated screenshot reference for 404s."""
    return CustomerSuccessService().screenshot_asset_audit()


@router.get("/image-rendering", response_model=ImageRenderingReport)
async def get_docs_image_rendering(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """Sprint 56F.8 — end-to-end verification that article images render."""
    engine = DocumentationImageVerificationEngine(session)
    return await engine.verify(org_context.requires_organization)


@router.post("/image-rendering/repair", response_model=ImageRenderingRepairResult)
async def repair_docs_image_rendering(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """Sprint 56F.8 — rewrite stale article image URLs to canonical form."""
    engine = DocumentationImageVerificationEngine(session)
    return await engine.repair(org_context.requires_organization)
