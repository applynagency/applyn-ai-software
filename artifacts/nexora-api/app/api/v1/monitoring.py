"""Sprint 42A — Continuous Monitoring API (read-only + manual poll trigger).

* GET  /v1/monitoring/alerts          — list ingested alerts
* GET  /v1/monitoring/alerts/{id}     — single alert
* GET  /v1/monitoring/dashboard       — Operations Center summary
* POST /v1/monitoring/poll            — admin/manual trigger of the poll cycle

Read-only monitoring: no deployments, remediation, mutations, or shell exec.
All lookups are organization-scoped (cross-org → 404).
"""

from fastapi import APIRouter, HTTPException, Query, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.core.config import settings
from app.schemas.monitoring import (
    DeadLetterResponse,
    IngestionMetrics,
    MonitoringAlertInvestigateResponse,
    MonitoringAlertListResponse,
    MonitoringAlertResponse,
    MonitoringDashboardResponse,
    MonitoringPollRequest,
    MonitoringPollResponse,
    MonitoringWebhookRequest,
)
from app.services.monitoring import MonitoringEngine
from app.services.monitoring_ingestion import IngestError

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


@router.get("/alerts", response_model=MonitoringAlertListResponse)
async def list_alerts(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    status_filter: str | None = Query(default=None, alias="status"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
):
    engine = MonitoringEngine(session)
    items, total = await engine.list_alerts(
        current_user, org_context, status=status_filter, offset=offset, limit=limit
    )
    return MonitoringAlertListResponse(
        items=[MonitoringAlertResponse.model_validate(a) for a in items], total=total
    )


@router.get("/dashboard", response_model=MonitoringDashboardResponse)
async def get_dashboard(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    engine = MonitoringEngine(session)
    return await engine.dashboard(current_user, org_context)


@router.get("/alerts/{alert_id}", response_model=MonitoringAlertResponse)
async def get_alert(
    alert_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    engine = MonitoringEngine(session)
    alert = await engine.get_alert(current_user, org_context, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return MonitoringAlertResponse.model_validate(alert)


@router.post("/alerts/{alert_id}/investigate", response_model=MonitoringAlertInvestigateResponse)
async def investigate_alert(
    alert_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """Manually triage an alert → incident + AI investigation (any severity)."""
    engine = MonitoringEngine(session)
    result = await engine.investigate_alert(current_user, org_context, alert_id)
    return MonitoringAlertInvestigateResponse(**result)


@router.post("/poll", response_model=MonitoringPollResponse)
async def poll(
    data: MonitoringPollRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    # Async path: only provider polling is offloaded. Inline alert injection
    # (``data.alerts``) stays synchronous as it is request-scoped test/admin input.
    if settings.JOB_QUEUE_ENABLED and not data.alerts:
        from app.jobs.submit import accepted_response, submit_job
        from app.models.job import JobType

        org_id = org_context.requires_organization
        kwargs = {
            "organization_id": org_id, "user_id": current_user.id,
            "providers": data.providers,
        }
        job = await submit_job(
            session, task_name="run_monitoring_poll", job_type=JobType.MONITORING_POLL,
            organization_id=org_id, user_id=current_user.id, params=kwargs, task_kwargs=kwargs,
        )
        return accepted_response(job)
    engine = MonitoringEngine(session)
    summary = await engine.poll(
        current_user,
        org_context,
        provided_alerts=data.alerts,
        providers=data.providers,
    )
    return _poll_response(summary)


@router.post("/ingest", response_model=MonitoringPollResponse)
async def ingest_webhook(
    data: MonitoringWebhookRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """Push-based ingestion of a provider alert webhook (Alertmanager/Prometheus,
    CloudWatch via SNS, Azure Monitor, GitHub Actions, GitLab pipelines).

    Org-scoped via the authenticated context (multi-tenant safe). Malformed
    payloads are dead-lettered and return 422."""
    engine = MonitoringEngine(session)
    try:
        summary = await engine.ingest_webhook(
            current_user, org_context, data.provider, data.payload
        )
    except IngestError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return _poll_response(summary)


@router.get("/dead-letters", response_model=list[DeadLetterResponse])
async def list_dead_letters(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
):
    engine = MonitoringEngine(session)
    rows = await engine.list_dead_letters(
        current_user, org_context, status=status_filter, limit=limit
    )
    return [DeadLetterResponse.model_validate(r) for r in rows]


def _poll_response(summary: dict) -> MonitoringPollResponse:
    metrics = summary.get("metrics") or {}
    return MonitoringPollResponse(
        polled_providers=summary["polled_providers"],
        alerts_ingested=summary["alerts_ingested"],
        new_alerts=summary["new_alerts"],
        deduplicated=summary["deduplicated"],
        incidents_created=summary["incidents_created"],
        notifications_sent=summary["notifications_sent"],
        alerts=[MonitoringAlertResponse.model_validate(a) for a in summary["alerts"]],
        metrics=IngestionMetrics(**metrics) if metrics else IngestionMetrics(),
    )
