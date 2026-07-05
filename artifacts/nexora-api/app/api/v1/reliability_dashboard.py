"""Sprint 45B - Executive Reliability Dashboard API.

* GET /v1/reliability-dashboard          - aggregated metrics, score & trends
* GET /v1/reliability-dashboard/summary  - executive summary (text + highlights)
* GET /v1/reliability-dashboard/export   - export report (pdf | html | markdown)

Views: organization (default) | team | service, via ?scope= and ?value=.
Trend windows: 7 / 30 / 90 days via ?window=. Read-only, org-scoped, audited.
"""

from fastapi import APIRouter, Query, Response

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.reliability_dashboard import (
    ExecutiveSummaryResponse,
    ReliabilityDashboardResponse,
)
from app.services.reliability_dashboard import ReliabilityDashboardService

router = APIRouter(prefix="/reliability-dashboard", tags=["Executive Reliability Dashboard"])


@router.get("", response_model=ReliabilityDashboardResponse)
async def get_dashboard(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    scope: str = Query(default="organization"),
    value: str | None = Query(default=None),
    window: int = Query(default=30),
):
    return await ReliabilityDashboardService(session).dashboard(
        current_user, org_context, scope=scope, scope_value=value, window_days=window
    )


@router.get("/summary", response_model=ExecutiveSummaryResponse)
async def get_summary(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    scope: str = Query(default="organization"),
    value: str | None = Query(default=None),
    window: int = Query(default=30),
):
    return await ReliabilityDashboardService(session).summary(
        current_user, org_context, scope=scope, scope_value=value, window_days=window
    )


@router.get("/export")
async def export_dashboard(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    scope: str = Query(default="organization"),
    value: str | None = Query(default=None),
    window: int = Query(default=30),
    format: str = Query(default="pdf"),
):
    content, media_type, filename = await ReliabilityDashboardService(session).export(
        current_user, org_context, scope=scope, scope_value=value, window_days=window, fmt=format
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
