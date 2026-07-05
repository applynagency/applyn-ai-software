"""Sprint 46C - Executive Reliability Reporting API.

* POST /v1/executive-reports/generate   - generate a weekly/monthly/quarterly report
* GET  /v1/executive-reports            - list reports (optional ?report_type=)
* GET  /v1/executive-reports/{id}       - full report (metrics, trend, action plan)
* GET  /v1/executive-reports/{id}/export - export report (pdf | html | markdown)

Read-only aggregation; org-scoped and audited.
"""

from fastapi import APIRouter, Query, Response, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.core.config import settings
from app.schemas.executive_report import (
    ExecutiveReportResponse,
    ExecutiveReportSummary,
    ReportGenerateRequest,
)
from app.services.executive_report import ExecutiveReportingService

router = APIRouter(prefix="/executive-reports", tags=["Executive Reporting"])


@router.post("/generate", response_model=ExecutiveReportResponse, status_code=status.HTTP_201_CREATED)
async def generate_report(
    payload: ReportGenerateRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    if settings.JOB_QUEUE_ENABLED:
        from app.jobs.submit import accepted_response, submit_job
        from app.models.job import JobType

        org_id = org_context.requires_organization
        kwargs = {
            "organization_id": org_id, "user_id": current_user.id,
            "report_type": payload.report_type,
        }
        job = await submit_job(
            session, task_name="run_executive_report", job_type=JobType.EXECUTIVE_REPORT,
            organization_id=org_id, user_id=current_user.id, params=kwargs, task_kwargs=kwargs,
        )
        return accepted_response(job)
    return await ExecutiveReportingService(session).generate(
        current_user, org_context, report_type=payload.report_type
    )


@router.get("", response_model=list[ExecutiveReportSummary])
async def list_reports(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    report_type: str | None = Query(default=None),
):
    rows = await ExecutiveReportingService(session).list(
        current_user, org_context, report_type=report_type
    )
    return [ExecutiveReportSummary.model_validate(r) for r in rows]


@router.get("/{report_id}", response_model=ExecutiveReportResponse)
async def get_report(
    report_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await ExecutiveReportingService(session).get(current_user, org_context, report_id)


@router.get("/{report_id}/export")
async def export_report(
    report_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    format: str = Query(default="pdf"),
):
    content, media_type, filename = await ExecutiveReportingService(session).export(
        current_user, org_context, report_id, fmt=format
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
