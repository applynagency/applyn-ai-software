"""Multi-cloud & Kubernetes control plane REST API."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.core.config import settings
from app.schemas.control_plane import (
    CloudAccountCreate,
    CloudAccountView,
    CloudSyncResult,
    ClusterCreate,
    ClusterResourceView,
    ClusterView,
    CostView,
    GitOpsAppView,
    HelmReleaseView,
    InventoryItemView,
    OperationCreate,
    OperationDecision,
    OperationView,
    PolicyFindingView,
)
from app.services.control_plane import ControlPlaneService

router = APIRouter(prefix="/control-plane", tags=["Control Plane"])


def _svc(session) -> ControlPlaneService:
    return ControlPlaneService(session)


@router.get("/providers")
async def list_providers():
    return ControlPlaneService.supported_providers()


# --- Cloud accounts ---------------------------------------------------------
@router.get("/cloud-accounts", response_model=list[CloudAccountView])
async def list_cloud_accounts(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_cloud_accounts(current_user, org_context)
    return [CloudAccountView.model_validate(r) for r in rows]


@router.post("/cloud-accounts", response_model=CloudAccountView, status_code=status.HTTP_201_CREATED)
async def register_cloud_account(
    payload: CloudAccountCreate, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).register_cloud_account(
        current_user, org_context, payload.credential_id, payload.display_name,
    )
    await session.commit()
    return CloudAccountView.model_validate(row)


@router.post("/cloud-accounts/{account_id}/sync", response_model=CloudSyncResult)
async def sync_cloud_account(
    account_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    run = await _svc(session).sync_cloud_account(current_user, org_context, account_id)
    await session.commit()
    return CloudSyncResult(sync_run_id=run.id, status=run.status, resources_total=run.resources_total)


# --- Clusters ---------------------------------------------------------------
@router.get("/clusters", response_model=list[ClusterView])
async def list_clusters(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_clusters(current_user, org_context)
    return [ClusterView.model_validate(r) for r in rows]


@router.post("/clusters", response_model=ClusterView, status_code=status.HTTP_201_CREATED)
async def register_cluster(
    payload: ClusterCreate, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).register_cluster(
        current_user, org_context, payload.credential_id, payload.name,
        payload.distribution, payload.cloud_account_id,
    )
    await session.commit()
    return ClusterView.model_validate(row)


@router.get("/clusters/{cluster_id}", response_model=ClusterView)
async def get_cluster(
    cluster_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).get_cluster(current_user, org_context, cluster_id)
    return ClusterView.model_validate(row)


@router.post("/clusters/{cluster_id}/discover")
async def discover_cluster(
    cluster_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    run = await _svc(session).discover_cluster(current_user, org_context, cluster_id)
    await session.commit()
    return {"discovery_run_id": run.id, "status": run.status, "resource_count": run.resource_count}


@router.get("/clusters/{cluster_id}/resources", response_model=list[ClusterResourceView])
async def list_cluster_resources(
    cluster_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
    kind: str | None = None, namespace: str | None = None,
):
    rows = await _svc(session).list_cluster_resources(
        current_user, org_context, cluster_id, kind=kind, namespace=namespace,
    )
    return [ClusterResourceView.model_validate(r) for r in rows]


@router.get("/clusters/{cluster_id}/policies", response_model=list[PolicyFindingView])
async def list_policies(
    cluster_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    rows = await _svc(session).list_policy_findings(current_user, org_context, cluster_id)
    return [PolicyFindingView.model_validate(r) for r in rows]


@router.get("/clusters/{cluster_id}/helm", response_model=list[HelmReleaseView])
async def list_helm(
    cluster_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    releases = await _svc(session).list_helm_releases(current_user, org_context, cluster_id)
    return [HelmReleaseView(name=r.name, namespace=r.namespace, chart=r.chart,
                            version=r.version, status=r.status, revision=r.revision) for r in releases]


@router.get("/clusters/{cluster_id}/gitops", response_model=list[GitOpsAppView])
async def list_gitops(
    cluster_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    apps = await _svc(session).list_gitops_apps(current_user, org_context, cluster_id)
    return [GitOpsAppView(engine=a.engine, name=a.name, namespace=a.namespace,
                          sync_status=a.sync_status, health=a.health, revision=a.revision,
                          drift=a.drift) for a in apps]


@router.post("/clusters/{cluster_id}/read")
async def cluster_read(
    cluster_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
    action: str = Query(...), namespace: str | None = None, name: str | None = None,
):
    result = await _svc(session).read_cluster(
        current_user, org_context, cluster_id, action,
        {"namespace": namespace, "name": name},
    )
    await session.commit()
    return result


# --- Operations (approval-gated) --------------------------------------------
@router.get("/operations", response_model=list[OperationView])
async def list_operations(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_operations(current_user, org_context)
    return [OperationView.model_validate(r) for r in rows]


@router.post("/operations", response_model=OperationView, status_code=status.HTTP_201_CREATED)
async def propose_operation(
    payload: OperationCreate, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).propose_operation(current_user, org_context, payload)
    await session.commit()
    return OperationView.model_validate(row)


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


# --- Unified inventory & costs ----------------------------------------------
@router.get("/inventory", response_model=list[InventoryItemView])
async def unified_inventory(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).unified_inventory(current_user, org_context)
    return [InventoryItemView(**r) for r in rows]


@router.get("/cloud-accounts/{account_id}/costs", response_model=CostView)
async def cloud_costs(
    account_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    svc = _svc(session)
    org_id = org_context.requires_organization
    account = await svc.cloud_accounts.get_by_id(account_id)
    if not account or account.organization_id != org_id:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("CloudAccount", account_id)
    summary = account.cost_summary or {}
    return CostView(
        scope_type="cloud", scope_id=account_id,
        currency=summary.get("currency", "USD"), period_days=30,
        total_estimate=float(summary.get("total_estimate", 0)),
        breakdown=summary.get("by_service", {}),
        opportunities=summary.get("rightsizing_opportunities", []),
    )
