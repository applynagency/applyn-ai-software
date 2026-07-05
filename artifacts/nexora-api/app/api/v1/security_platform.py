"""Enterprise DevSecOps & Cloud Security Platform REST API (Sprint 65D/65E)."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.security_platform import (
    AnalyticsView,
    BackfillStatusView,
    ComplianceView,
    ExceptionCreate,
    ExceptionView,
    FindingTransition,
    FindingView,
    IdentitySecurityView,
    InvestigationCreate,
    InvestigationView,
    OverviewView,
    ProviderCreate,
    ProvidersView,
    ProviderView,
    RemediationExecutionView,
    RemediationProposalCreate,
    RemediationProposalView,
    SbomComponentView,
    SbomImportRequest,
    SbomView,
    ScanRequest,
    ScanRunView,
    SlaView,
)
from app.services.security_platform import SecurityPlatformService

router = APIRouter(prefix="/security", tags=["Enterprise Security"])


def _svc(session) -> SecurityPlatformService:
    return SecurityPlatformService(session)


@router.get("/providers", response_model=ProvidersView)
async def list_provider_catalog():
    return ProvidersView(**SecurityPlatformService.providers())


@router.get("/providers/config", response_model=list[ProviderView])
async def list_provider_configs(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_provider_configs(current_user, org_context)
    await session.commit()
    return [ProviderView.model_validate(r) for r in rows]


@router.post("/providers", response_model=ProviderView, status_code=status.HTTP_201_CREATED)
async def create_provider(
    payload: ProviderCreate, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).create_provider(current_user, org_context, payload)
    await session.commit()
    return ProviderView.model_validate(row)


@router.post("/providers/{provider_id}/validate", response_model=ProviderView)
async def validate_provider(
    provider_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).validate_provider_config(current_user, org_context, provider_id)
    await session.commit()
    return ProviderView.model_validate(row)


@router.post("/backfill/dry-run", response_model=BackfillStatusView)
async def backfill_dry_run(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    job = await _svc(session).backfill_dry_run(current_user, org_context)
    await session.commit()
    return BackfillStatusView.model_validate(job)


@router.post("/backfill/execute", response_model=BackfillStatusView)
async def backfill_execute(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    job = await _svc(session).backfill_execute(current_user, org_context)
    await session.commit()
    return BackfillStatusView.model_validate(job)


@router.get("/backfill/status", response_model=BackfillStatusView | None)
async def backfill_status(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    job = await _svc(session).backfill_status(current_user, org_context)
    await session.commit()
    return BackfillStatusView.model_validate(job) if job else None


@router.get("/sla", response_model=SlaView)
async def get_sla(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).get_sla_view(current_user, org_context)
    await session.commit()
    return SlaView(**data)


@router.post("/sla/evaluate")
async def evaluate_sla(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).evaluate_slas(current_user, org_context)
    await session.commit()
    return data


@router.get("/overview", response_model=OverviewView)
async def overview(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).overview(current_user, org_context)
    await session.commit()
    return OverviewView(**data)


@router.post("/scans", response_model=ScanRunView, status_code=status.HTTP_201_CREATED)
async def run_scan(
    payload: ScanRequest, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).run_scan(current_user, org_context, payload)
    await session.commit()
    return ScanRunView.model_validate(row)


@router.get("/scan-runs")
async def list_scan_runs(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
    offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
):
    rows, total = await _svc(session).list_scans(current_user, org_context, offset=offset, limit=limit)
    await session.commit()
    return {
        "items": [ScanRunView.model_validate(r) for r in rows],
        "total": total, "offset": offset, "limit": limit,
    }


@router.get("/scans", response_model=list[ScanRunView])
async def list_scans(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows, _ = await _svc(session).list_scans(current_user, org_context)
    await session.commit()
    return [ScanRunView.model_validate(r) for r in rows]


@router.post("/scans/{scan_id}/execute", response_model=ScanRunView)
async def execute_scan(
    scan_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).execute_scan_by_id(current_user, org_context, scan_id)
    await session.commit()
    return ScanRunView.model_validate(row)


@router.post("/sbom/import")
async def import_sbom(
    payload: SbomImportRequest, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    data = await _svc(session).import_sbom(current_user, org_context, payload)
    await session.commit()
    return data


@router.get("/sbom/components")
async def list_sbom_components(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
    offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500),
):
    rows, total = await _svc(session).list_sbom_components(
        current_user, org_context, offset=offset, limit=limit,
    )
    await session.commit()
    return {
        "items": [SbomComponentView.model_validate(r) for r in rows],
        "total": total, "offset": offset, "limit": limit,
    }


@router.get("/findings")
async def list_findings(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
    status_filter: str | None = Query(None, alias="status"),
    severity: str | None = None, source: str | None = None,
    offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
):
    rows, total = await _svc(session).list_findings(
        current_user, org_context, status=status_filter, severity=severity,
        source=source, offset=offset, limit=limit,
    )
    await session.commit()
    return {
        "items": [FindingView.model_validate(r) for r in rows],
        "total": total, "offset": offset, "limit": limit,
    }


@router.post("/findings/{finding_id}/transition", response_model=FindingView)
async def transition_finding(
    finding_id: str, payload: FindingTransition,
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).transition_finding(current_user, org_context, finding_id, payload)
    await session.commit()
    return FindingView.model_validate(row)


@router.get("/vulnerabilities")
async def vulnerabilities(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).vulnerabilities(current_user, org_context)
    await session.commit()
    return data


@router.get("/sbom", response_model=list[SbomView])
async def sbom_inventory(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).sbom_inventory(current_user, org_context)
    await session.commit()
    return [SbomView.model_validate(r) for r in rows]


@router.get("/kubernetes")
async def kubernetes_security(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).kubernetes_security(current_user, org_context)
    await session.commit()
    return data


@router.get("/cloud")
async def cloud_posture(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).cloud_posture(current_user, org_context)
    await session.commit()
    return data


@router.get("/iac")
async def iac_security(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).iac_security(current_user, org_context)
    await session.commit()
    return data


@router.get("/identity", response_model=IdentitySecurityView)
async def identity_security(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).identity_security(current_user, org_context)
    await session.commit()
    return IdentitySecurityView(**data)


@router.get("/compliance", response_model=ComplianceView)
async def compliance(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).compliance_view(current_user, org_context)
    await session.commit()
    return ComplianceView(**data)


@router.get("/exceptions", response_model=list[ExceptionView])
async def list_exceptions(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_exceptions(current_user, org_context)
    await session.commit()
    return [ExceptionView.model_validate(r) for r in rows]


@router.post("/exceptions", response_model=ExceptionView, status_code=status.HTTP_201_CREATED)
async def grant_exception(
    payload: ExceptionCreate, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).grant_exception(current_user, org_context, payload)
    await session.commit()
    return ExceptionView.model_validate(row)


@router.get("/remediation", response_model=list[RemediationProposalView])
async def list_remediations(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_remediations(current_user, org_context)
    await session.commit()
    return [RemediationProposalView.model_validate(r) for r in rows]


@router.post("/remediation", response_model=RemediationProposalView, status_code=status.HTTP_201_CREATED)
async def propose_remediation(
    payload: RemediationProposalCreate,
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).propose_remediation(current_user, org_context, payload)
    await session.commit()
    return RemediationProposalView.model_validate(row)


@router.post("/remediation/{proposal_id}/decide", response_model=RemediationProposalView)
async def decide_remediation(
    proposal_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    approved: bool = True,
):
    row = await _svc(session).approve_remediation(current_user, org_context, proposal_id, approved=approved)
    await session.commit()
    return RemediationProposalView.model_validate(row)


@router.get("/remediation/{proposal_id}/execution", response_model=RemediationExecutionView)
async def get_remediation_execution(
    proposal_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).get_remediation_execution(current_user, org_context, proposal_id)
    await session.commit()
    return RemediationExecutionView.model_validate(row)


@router.post("/remediation/{proposal_id}/execute", response_model=RemediationExecutionView)
async def execute_remediation(
    proposal_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).execute_remediation(current_user, org_context, proposal_id)
    await session.commit()
    return RemediationExecutionView.model_validate(row)


@router.get("/analytics", response_model=AnalyticsView)
async def analytics(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).analytics(current_user, org_context)
    await session.commit()
    return AnalyticsView(**data)


@router.post("/investigations", response_model=InvestigationView, status_code=status.HTTP_201_CREATED)
async def create_investigation(
    payload: InvestigationCreate,
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).investigate(current_user, org_context, payload)
    await session.commit()
    return InvestigationView.model_validate(row)


@router.get("/investigations", response_model=list[InvestigationView])
async def list_investigations(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_investigations(current_user, org_context)
    await session.commit()
    return [InvestigationView.model_validate(r) for r in rows]
