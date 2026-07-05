"""Sprint 52C.1 — Sales Demo Mode API.

GET /v1/demo/sales-mode

Returns a fully populated presentation-ready dashboard:
  • All demo organisations owned by the authenticated user
  • Available scenarios and completion status
  • Business-value callouts
  • 10-step guided walkthrough
  • Screenshot manifest

Designed for live sales calls, investor demos, and onboarding sessions.
No organisation context needed — aggregates across all demo orgs the user owns.
"""

from fastapi import APIRouter

from app.auth.dependencies import CurrentUser, DBSession
from app.schemas.demo_scenario import SalesDashboardResponse
from app.services.demo_sales_mode import DemoSalesModeService

router = APIRouter(prefix="/demo", tags=["Demo Sales Mode"])


@router.get("/sales-mode", response_model=SalesDashboardResponse)
async def get_sales_mode(
    current_user: CurrentUser,
    session: DBSession,
):
    """
    Return a presentation-ready sales demo dashboard.

    Aggregates all demo organisations, scenarios, walkthrough steps,
    value callouts, and asset manifests for the authenticated user.
    No real infrastructure or credentials required.
    """
    svc = DemoSalesModeService(session)
    return await svc.get_sales_dashboard(current_user)
