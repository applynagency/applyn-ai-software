"""DevOps delivery platform REST API."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.delivery import (
    ArtifactView,
    DashboardView,
    DeploymentDetailView,
    DeploymentIncidentLink,
    DeploymentListResponse,
    DeploymentView,
    DoraMetricsView,
    EnvironmentView,
    GitOpsAppView,
    OperationCreate,
    OperationDecision,
    OperationView,
    PipelineRunView,
    PipelineView,
    ReleaseCreate,
    ReleaseView,
    RepositoryView,
    SecurityScanRequest,
    SecurityScanView,
    SourceConnectionCreate,
    SourceConnectionView,
)
from app.services.delivery import DeliveryService

router = APIRouter(prefix="/delivery", tags=["Delivery"])


def _svc(session) -> DeliveryService:
    return DeliveryService(session)


@router.get("/providers")
async def list_providers():
    return DeliveryService.supported_providers()


@router.get("/dashboard", response_model=DashboardView)
async def dashboard(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).dashboard(current_user, org_context)
    return DashboardView(
        repositories=data["repositories"],
        pipelines=data["pipelines"],
        deployments=data["deployments"],
        releases=data["releases"],
        environments=data["environments"],
        gitops_apps=data["gitops_apps"],
        security_scans=data["security_scans"],
        pending_operations=data["pending_operations"],
        dora=DoraMetricsView(**data["dora"].__dict__),
    )


@router.get("/dora", response_model=DoraMetricsView)
async def dora_metrics(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
    window_days: int = Query(30, ge=7, le=90),
):
    m = await _svc(session).dora_metrics(current_user, org_context, window_days=window_days)
    return DoraMetricsView(**m.__dict__)


# --- Source control ---------------------------------------------------------
@router.get("/source-connections", response_model=list[SourceConnectionView])
async def list_source_connections(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_connections(current_user, org_context)
    return [SourceConnectionView.model_validate(r) for r in rows]


@router.post("/source-connections", response_model=SourceConnectionView, status_code=status.HTTP_201_CREATED)
async def connect_source(
    payload: SourceConnectionCreate, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).connect_source(
        current_user, org_context, payload.credential_id, payload.display_name,
    )
    await session.commit()
    return SourceConnectionView.model_validate(row)


@router.post("/source-connections/{connection_id}/sync")
async def sync_repositories(
    connection_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    result = await _svc(session).sync_repositories(current_user, org_context, connection_id)
    await session.commit()
    return result


@router.get("/repositories", response_model=list[RepositoryView])
async def list_repositories(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_repositories(current_user, org_context)
    return [RepositoryView.model_validate(r) for r in rows]


@router.get("/repositories/{repo_id}")
async def get_repository(
    repo_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    detail = await _svc(session).get_repository_detail(current_user, org_context, repo_id)
    repo = detail["repository"]
    return {
        "repository": RepositoryView.model_validate(repo),
        "branches": [{"name": b.name, "commit_sha": b.commit_sha, "protected": b.protected}
                     for b in detail["branches"]],
        "commits": [{"sha": c.sha, "message": c.message, "author": c.author, "committed_at": c.committed_at}
                    for c in detail["commits"]],
        "pull_requests": [{"number": p.number, "title": p.title, "state": p.state, "author": p.author,
                           "source_branch": p.source_branch, "target_branch": p.target_branch, "url": p.url}
                          for p in detail["pull_requests"]],
    }


# --- Pipelines --------------------------------------------------------------
@router.get("/pipelines", response_model=list[PipelineView])
async def list_pipelines(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_pipelines(current_user, org_context)
    return [PipelineView.model_validate(r) for r in rows]


@router.post("/repositories/{repository_id}/pipelines/sync")
async def sync_pipelines(
    repository_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    result = await _svc(session).sync_pipelines(current_user, org_context, repository_id)
    await session.commit()
    return result


@router.get("/pipeline-runs", response_model=list[PipelineRunView])
async def list_pipeline_runs(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_pipeline_runs(current_user, org_context)
    return [PipelineRunView.model_validate(r) for r in rows]


@router.post("/pipelines/{pipeline_id}/runs/sync")
async def sync_pipeline_runs(
    pipeline_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    result = await _svc(session).sync_pipeline_runs(current_user, org_context, pipeline_id)
    await session.commit()
    return result


# --- Artifacts --------------------------------------------------------------
@router.post("/artifacts/sync")
async def sync_artifacts(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
    registry: str = Query(...), credential_id: str = Query(...),
):
    result = await _svc(session).sync_artifacts(current_user, org_context, registry, credential_id)
    await session.commit()
    return result


@router.get("/artifacts", response_model=list[ArtifactView])
async def list_artifacts(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_artifacts(current_user, org_context)
    return [ArtifactView.model_validate(r) for r in rows]


# --- Environments -----------------------------------------------------------
@router.get("/environments", response_model=list[EnvironmentView])
async def list_environments(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_environments(current_user, org_context)
    await session.commit()
    return [EnvironmentView.model_validate(r) for r in rows]


# --- Releases ---------------------------------------------------------------
@router.get("/releases", response_model=list[ReleaseView])
async def list_releases(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_releases(current_user, org_context)
    return [ReleaseView.model_validate(r) for r in rows]


@router.post("/releases", response_model=ReleaseView, status_code=status.HTTP_201_CREATED)
async def create_release(
    payload: ReleaseCreate, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).create_release(current_user, org_context, payload)
    await session.commit()
    return ReleaseView.model_validate(row)


@router.post("/releases/{release_id}/approve", response_model=ReleaseView)
async def approve_release(
    release_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).approve_release(current_user, org_context, release_id)
    await session.commit()
    return ReleaseView.model_validate(row)


# --- Deployments & operations -----------------------------------------------
@router.get("/linked-incidents", response_model=list[DeploymentIncidentLink])
async def list_linked_incidents(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    limit: int = Query(10, ge=1, le=50),
):
    rows = await _svc(session).list_linked_incidents(current_user, org_context, limit=limit)
    return [DeploymentIncidentLink.model_validate(r) for r in rows]


@router.get("/deployments", response_model=list[DeploymentView] | DeploymentListResponse)
async def list_deployments(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int | None = Query(None, ge=0),
    limit: int | None = Query(None, ge=1, le=200),
    status: str | None = None,
    environment_id: str | None = None,
    service: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    paginated: bool = Query(False),
):
    svc = _svc(session)
    if paginated or offset is not None or limit is not None or status or environment_id or service or date_from or date_to:
        data = await svc.list_deployments_paginated(
            current_user,
            org_context,
            offset=offset or 0,
            limit=limit or 50,
            status=status,
            environment_id=environment_id,
            service=service,
            date_from=date_from,
            date_to=date_to,
        )
        return DeploymentListResponse(
            items=[DeploymentView.model_validate(r) for r in data["items"]],
            total=data["total"],
            offset=data["offset"],
            limit=data["limit"],
        )
    rows = await svc.list_deployments(current_user, org_context)
    return [DeploymentView.model_validate(r) for r in rows]


@router.get("/deployments/{deployment_id}", response_model=DeploymentDetailView)
async def get_deployment(
    deployment_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    detail = await _svc(session).get_deployment_detail(current_user, org_context, deployment_id)
    return DeploymentDetailView(
        deployment=DeploymentView.model_validate(detail["deployment"]),
        environment_name=detail["environment_name"],
        environment_tier=detail["environment_tier"],
        release=ReleaseView.model_validate(detail["release"]) if detail["release"] else None,
        linked_operations=[OperationView.model_validate(o) for o in detail["linked_operations"]],
        linked_incidents=[DeploymentIncidentLink.model_validate(i) for i in detail["linked_incidents"]],
        rollback_plan=detail["rollback_plan"],
    )


@router.post("/operations", response_model=OperationView, status_code=status.HTTP_201_CREATED)
async def propose_operation(
    payload: OperationCreate, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).propose_operation(current_user, org_context, payload)
    await session.commit()
    return OperationView.model_validate(row)


@router.get("/operations", response_model=list[OperationView])
async def list_operations(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_operations(current_user, org_context)
    return [OperationView.model_validate(r) for r in rows]


@router.post("/operations/{operation_id}/decide", response_model=OperationView)
async def decide_operation(
    operation_id: str, payload: OperationDecision,
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).decide_operation(
        current_user, org_context, operation_id, payload.approved,
    )
    await session.commit()
    return OperationView.model_validate(row)


@router.post("/operations/{operation_id}/execute", response_model=OperationView)
async def execute_operation(
    operation_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).execute_operation(current_user, org_context, operation_id)
    await session.commit()
    return OperationView.model_validate(row)


# --- Security ---------------------------------------------------------------
@router.post("/security/scans", response_model=SecurityScanView, status_code=status.HTTP_201_CREATED)
async def run_security_scan(
    payload: SecurityScanRequest, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).run_scan(current_user, org_context, payload)
    await session.commit()
    return SecurityScanView.model_validate(row)


@router.get("/security/scans", response_model=list[SecurityScanView])
async def list_security_scans(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_scans(current_user, org_context)
    return [SecurityScanView.model_validate(r) for r in rows]


# --- GitOps -----------------------------------------------------------------
@router.post("/gitops/sync")
async def sync_gitops(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
    cluster_name: str = Query("prod"),
):
    result = await _svc(session).sync_gitops(current_user, org_context, cluster_name)
    await session.commit()
    return result


@router.post("/gitops/apps/{app_name}/sync")
async def trigger_gitops_app_sync(
    app_name: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    revision: str | None = Query(None),
    prune: bool = Query(False),
    engine: str = Query("ArgoCD"),
):
    result = await _svc(session).trigger_gitops_app_sync(
        current_user, org_context, app_name, revision=revision, prune=prune, engine=engine,
    )
    await session.commit()
    return result


@router.post("/gitops/apps/{app_name}/rollback")
async def trigger_gitops_app_rollback(
    app_name: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    revision_id: int = Query(..., ge=1),
    engine: str = Query("ArgoCD"),
):
    result = await _svc(session).trigger_gitops_app_rollback(
        current_user, org_context, app_name, revision_id, engine=engine,
    )
    await session.commit()
    return result


@router.get("/gitops", response_model=list[GitOpsAppView])
async def list_gitops(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_gitops(current_user, org_context)
    return [GitOpsAppView.model_validate(r) for r in rows]


# --- Release Reliability (Sprint 65F) ---------------------------------------
from app.schemas.release_reliability import (
    FreezeWindowCreate,
    FreezeWindowView,
    PromotionPolicyCreate,
    PromotionPolicyView,
    ReleaseReliabilityCreate,
    ReleaseReliabilityView,
    RolloutPropose,
    VerificationEvidenceView,
)
from app.services.release_reliability import ReleaseReliabilityService


def _rr_svc(session) -> ReleaseReliabilityService:
    return ReleaseReliabilityService(session)


@router.get("/release-reliability")
async def list_release_reliability(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
    offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
):
    rows, total = await _rr_svc(session).list_reliability(current_user, org_context, offset=offset, limit=limit)
    await session.commit()
    return {
        "items": [ReleaseReliabilityView.model_validate(r) for r in rows],
        "total": total, "offset": offset, "limit": limit,
    }


@router.post("/release-reliability", response_model=ReleaseReliabilityView, status_code=status.HTTP_201_CREATED)
async def create_release_reliability(
    payload: ReleaseReliabilityCreate,
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _rr_svc(session).create(current_user, org_context, payload)
    await session.commit()
    return ReleaseReliabilityView.model_validate(row)


@router.get("/release-reliability/{reliability_id}", response_model=ReleaseReliabilityView)
async def get_release_reliability(
    reliability_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _rr_svc(session).get_reliability(current_user, org_context, reliability_id)
    await session.commit()
    return ReleaseReliabilityView.model_validate(row)


@router.post("/release-reliability/{reliability_id}/verify")
async def verify_release(
    reliability_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    data = await _rr_svc(session).verify(current_user, org_context, reliability_id)
    await session.commit()
    return data


@router.get("/release-reliability/{reliability_id}/evidence", response_model=VerificationEvidenceView)
async def get_release_evidence(
    reliability_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    data = await _rr_svc(session).get_evidence(current_user, org_context, reliability_id)
    await session.commit()
    return VerificationEvidenceView(**data)


@router.post("/release-reliability/{reliability_id}/propose-rollout")
async def propose_rollout(
    reliability_id: str, payload: RolloutPropose,
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _rr_svc(session).propose_rollout(current_user, org_context, reliability_id, payload)
    await session.commit()
    return {"id": row.id, "status": row.status, "simulated": row.simulated, "result": row.result}


@router.post("/release-reliability/{reliability_id}/pause")
async def pause_rollout(
    reliability_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _rr_svc(session).pause_rollout(current_user, org_context, reliability_id)
    await session.commit()
    return {"id": row.id, "action": row.action, "status": row.status}


@router.post("/release-reliability/{reliability_id}/resume")
async def resume_rollout(
    reliability_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _rr_svc(session).resume_rollout(current_user, org_context, reliability_id)
    await session.commit()
    return {"id": row.id, "action": row.action, "status": row.status}


@router.post("/release-reliability/{reliability_id}/promote")
async def promote_rollout(
    reliability_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _rr_svc(session).promote_rollout(current_user, org_context, reliability_id)
    await session.commit()
    return {"id": row.id, "action": row.action, "status": row.status}


@router.post("/release-reliability/{reliability_id}/abort")
async def abort_rollout(
    reliability_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _rr_svc(session).abort_rollout(current_user, org_context, reliability_id)
    await session.commit()
    return {"id": row.id, "action": row.action, "status": row.status}


@router.post("/release-reliability/{reliability_id}/rollback")
async def rollback_release(
    reliability_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
    target_revision: str | None = None,
):
    row = await _rr_svc(session).rollback(current_user, org_context, reliability_id, target_revision=target_revision)
    await session.commit()
    return {"id": row.id, "status": row.status, "target_revision": row.target_revision}


@router.get("/release-reliability/{reliability_id}/history")
async def release_history(
    reliability_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    data = await _rr_svc(session).get_history(current_user, org_context, reliability_id)
    await session.commit()
    return data


@router.get("/promotion-policies", response_model=list[PromotionPolicyView])
async def list_promotion_policies(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _rr_svc(session).list_promotion_policies(current_user, org_context)
    await session.commit()
    return [PromotionPolicyView.model_validate(r) for r in rows]


@router.post("/promotion-policies", response_model=PromotionPolicyView, status_code=status.HTTP_201_CREATED)
async def create_promotion_policy(
    payload: PromotionPolicyCreate, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _rr_svc(session).create_promotion_policy(current_user, org_context, payload)
    await session.commit()
    return PromotionPolicyView.model_validate(row)


@router.get("/promotion-queue")
async def promotion_queue(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _rr_svc(session).promotion_queue(current_user, org_context)
    await session.commit()
    return [{"id": r.id, "reliability_id": r.reliability_id, "status": r.status, "block_reason": r.block_reason} for r in rows]


@router.post("/release-reliability/{reliability_id}/request-promotion")
async def request_promotion(
    reliability_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
    target_environment_id: str = Query(...),
):
    row = await _rr_svc(session).request_promotion(
        current_user, org_context, reliability_id, target_environment_id=target_environment_id,
    )
    await session.commit()
    return {"id": row.id, "status": row.status, "block_reason": row.block_reason}


@router.get("/freeze-windows", response_model=list[FreezeWindowView])
async def list_freeze_windows(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _rr_svc(session).list_freeze_windows(current_user, org_context)
    await session.commit()
    return [FreezeWindowView.model_validate(r) for r in rows]


@router.post("/freeze-windows", response_model=FreezeWindowView, status_code=status.HTTP_201_CREATED)
async def create_freeze_window(
    payload: FreezeWindowCreate, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _rr_svc(session).create_freeze_window(current_user, org_context, payload)
    await session.commit()
    return FreezeWindowView.model_validate(row)


@router.get("/release-analytics")
async def release_analytics(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _rr_svc(session).release_analytics(current_user, org_context)
    await session.commit()
    return data
