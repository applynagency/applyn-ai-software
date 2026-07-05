"""Sprint 53B — Executive ROI Calculator API.

* POST /v1/roi/calculate   - compute full ROI analysis from inputs
* GET  /v1/roi/assumptions - default improvement factors / economics
* POST /v1/roi/report      - rendered Markdown report (for the dashboard preview)
* POST /v1/roi/export      - export the report (pdf | html | markdown)

Read-only: the calculator reads and writes no business data. It is stateless
and only records an audit-log entry that a calculation was performed.
"""

from fastapi import APIRouter, Query, Response

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.repositories.audit import AuditLogRepository
from app.schemas.roi import ROIAssumptions, ROIRequest, ROIResult
from app.services.roi_calculator import ROICalculatorService, ROIInputs

router = APIRouter(prefix="/roi", tags=["ROI Calculator"])


def _to_inputs(payload: ROIRequest) -> ROIInputs:
    return ROIInputs(
        engineer_count=payload.engineer_count,
        average_salary=payload.average_salary,
        monthly_incidents=payload.monthly_incidents,
        average_mttr_hours=payload.average_mttr_hours,
        deployments_per_month=payload.deployments_per_month,
        oncall_burden_hours_per_week=payload.oncall_burden_hours_per_week,
        downtime_cost_per_hour=payload.downtime_cost_per_hour,
        platform_annual_cost=payload.platform_annual_cost,
        mttr_reduction_pct=payload.mttr_reduction_pct,
        incident_reduction_pct=payload.incident_reduction_pct,
        oncall_reduction_pct=payload.oncall_reduction_pct,
        deploy_hours_saved_each=payload.deploy_hours_saved_each,
    )


async def _audit(session, user, org_context, action: str, result: dict, fmt: str | None = None) -> None:
    details = {
        "organization_id": org_context.organization_id,
        "monthly_savings": result["outputs"]["monthly_savings"],
        "annual_savings": result["outputs"]["annual_savings"],
        "roi_percentage": result["outputs"]["roi_percentage"],
    }
    if fmt:
        details["format"] = fmt
    await AuditLogRepository(session).log(
        action=action,
        resource_type="roi_calculation",
        resource_id=user.id,
        user_id=user.id,
        details=details,
    )
    await session.commit()


@router.get("/assumptions", response_model=ROIAssumptions)
async def get_assumptions(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return ROICalculatorService(session).default_assumptions()


@router.post("/calculate", response_model=ROIResult)
async def calculate_roi(
    payload: ROIRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = ROICalculatorService(session)
    result = service.calculate(_to_inputs(payload))
    await _audit(session, current_user, org_context, "roi_calculated", result)
    return result


@router.post("/report")
async def render_report(
    payload: ROIRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = ROICalculatorService(session)
    result = service.calculate(_to_inputs(payload))
    markdown = service.render_markdown(result)
    return {
        "executive_summary": result["executive_summary"],
        "outputs": result["outputs"],
        "report_markdown": markdown,
    }


@router.post("/export")
async def export_report(
    payload: ROIRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    format: str = Query(default="pdf"),
):
    service = ROICalculatorService(session)
    result = service.calculate(_to_inputs(payload))
    content, media_type, filename = service.export(result, fmt=format)
    await _audit(session, current_user, org_context, "roi_report_exported", result, fmt=format)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
