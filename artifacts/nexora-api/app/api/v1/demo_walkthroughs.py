"""Sprint 52C.1 — Guided Walkthrough & Screenshot API.

GET /v1/demo-walkthroughs          - 10-step guided walkthrough for current org
GET /v1/demo-walkthroughs/screenshots - screenshot asset manifest

No organisation context required for the screenshot manifest (public static
catalogue).  The walkthrough itself is org-scoped.
"""

from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.demo_scenario import ScreenshotManifest, WalkthroughResponse
from app.services.demo_walkthrough import DemoWalkthroughService

router = APIRouter(prefix="/demo-walkthroughs", tags=["Demo Walkthroughs"])


@router.get("/screenshots", response_model=ScreenshotManifest)
async def get_screenshot_manifest(
    current_user: CurrentUser,
    session: DBSession,
):
    """Return the full manifest of walkthrough screenshot assets."""
    svc = DemoWalkthroughService()
    return svc.get_screenshot_manifest()


@router.get("", response_model=WalkthroughResponse)
async def get_walkthrough(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    scenario_type: str | None = Query(default=None, description="Optional scenario type filter."),
):
    """Return the 10-step guided walkthrough for the current demo organisation."""
    org_id = org_context.requires_organization
    svc = DemoWalkthroughService()
    return svc.get_walkthrough(org_id, scenario_type=scenario_type)
