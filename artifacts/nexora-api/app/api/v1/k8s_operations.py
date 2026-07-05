"""Advanced Kubernetes Operations REST API (Sprint 65A).

Extends Control Plane — mounted under /v1/control-plane/clusters/{cluster_id}/k8s
"""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.control_plane import OperationCreate, OperationDecision, OperationView
from app.schemas.k8s_operations import (
    DiagnosticsBundleView,
    DiagnosticsCollect,
    K8sOperationCreate,
    K8sOverviewView,
    K8sReadRequest,
)
from app.services.k8s_operations import K8sOperationsService

router = APIRouter(prefix="/control-plane/clusters", tags=["Kubernetes Operations"])


def _svc(session) -> K8sOperationsService:
    return K8sOperationsService(session)


@router.get("/{cluster_id}/k8s/capabilities")
async def k8s_capabilities(cluster_id: str):
    return {
        "read_actions": K8sOperationsService.supported_read_actions(),
        "write_kinds": K8sOperationsService.supported_write_kinds(),
    }


@router.get("/{cluster_id}/k8s/overview", response_model=K8sOverviewView)
async def k8s_overview(
    cluster_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    data = await _svc(session).overview(current_user, org_context, cluster_id)
    await session.commit()
    return K8sOverviewView(**data)


@router.post("/{cluster_id}/k8s/read")
async def k8s_read(
    cluster_id: str, payload: K8sReadRequest,
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    params = dict(payload.params or {})
    if payload.namespace:
        params["namespace"] = payload.namespace
    if payload.name:
        params["name"] = payload.name
    if payload.kind:
        params["kind"] = payload.kind
    result = await _svc(session).read(current_user, org_context, cluster_id, payload.action, params)
    await session.commit()
    return result


@router.get("/{cluster_id}/k8s/pods")
async def list_pods(
    cluster_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
    namespace: str | None = None,
):
    result = await _svc(session).read(
        current_user, org_context, cluster_id, "list_pods", {"namespace": namespace},
    )
    await session.commit()
    return result


@router.get("/{cluster_id}/k8s/nodes")
async def list_nodes(
    cluster_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    result = await _svc(session).read(current_user, org_context, cluster_id, "list_nodes", {})
    await session.commit()
    return result


@router.get("/{cluster_id}/k8s/namespaces")
async def list_namespaces(
    cluster_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    result = await _svc(session).read(current_user, org_context, cluster_id, "list_namespaces", {})
    await session.commit()
    return result


@router.get("/{cluster_id}/k8s/workloads/{workload_kind}")
async def list_workloads(
    cluster_id: str, workload_kind: str,
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
    namespace: str | None = None,
):
    action_map = {
        "deployments": "list_deployments", "statefulsets": "list_statefulsets",
        "daemonsets": "list_daemonsets", "replicasets": "list_replicasets",
        "jobs": "list_jobs", "cronjobs": "list_cronjobs",
    }
    action = action_map.get(workload_kind.lower())
    if not action:
        from app.core.exceptions import NexoraException
        raise NexoraException(f"Unknown workload kind: {workload_kind}", 400)
    result = await _svc(session).read(
        current_user, org_context, cluster_id, action, {"namespace": namespace},
    )
    await session.commit()
    return result


@router.get("/{cluster_id}/k8s/storage/{storage_kind}")
async def list_storage(
    cluster_id: str, storage_kind: str,
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
    namespace: str | None = None,
):
    action_map = {"pvc": "list_pvc", "pv": "list_pv", "storageclasses": "list_storageclasses"}
    action = action_map.get(storage_kind.lower(), "list_pvc")
    result = await _svc(session).read(
        current_user, org_context, cluster_id, action, {"namespace": namespace},
    )
    await session.commit()
    return result


@router.get("/{cluster_id}/k8s/networking/{net_kind}")
async def list_networking(
    cluster_id: str, net_kind: str,
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
    namespace: str | None = None,
):
    action_map = {
        "services": "list_services", "ingress": "list_ingress",
        "network-policies": "list_network_policies",
    }
    action = action_map.get(net_kind.lower(), "list_services")
    result = await _svc(session).read(
        current_user, org_context, cluster_id, action, {"namespace": namespace},
    )
    await session.commit()
    return result


@router.post(
    "/{cluster_id}/k8s/diagnostics",
    response_model=DiagnosticsBundleView,
    status_code=status.HTTP_201_CREATED,
)
async def collect_diagnostics(
    cluster_id: str, payload: DiagnosticsCollect,
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).collect_diagnostics(
        current_user, org_context, cluster_id,
        namespace=payload.namespace, name=payload.name, kind=payload.kind,
    )
    await session.commit()
    return DiagnosticsBundleView.model_validate(row)


@router.get("/{cluster_id}/k8s/diagnostics", response_model=list[DiagnosticsBundleView])
async def list_diagnostics(
    cluster_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    rows = await _svc(session).list_diagnostics(current_user, org_context, cluster_id)
    await session.commit()
    return [DiagnosticsBundleView.model_validate(r) for r in rows]


@router.post("/{cluster_id}/k8s/operations", response_model=OperationView, status_code=status.HTTP_201_CREATED)
async def propose_k8s_operation(
    cluster_id: str, payload: K8sOperationCreate,
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).propose(
        current_user, org_context,
        OperationCreate(
            kind=payload.kind, cluster_id=cluster_id,
            namespace=payload.namespace, resource_name=payload.resource_name, params=payload.params,
        ),
    )
    await session.commit()
    return OperationView.model_validate(row)


@router.post("/{cluster_id}/k8s/operations/{operation_id}/decide", response_model=OperationView)
async def decide_k8s_operation(
    cluster_id: str, operation_id: str, payload: OperationDecision,
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).decide(current_user, org_context, operation_id, payload.approved)
    await session.commit()
    return OperationView.model_validate(row)


@router.post("/{cluster_id}/k8s/operations/{operation_id}/execute", response_model=OperationView)
async def execute_k8s_operation(
    cluster_id: str, operation_id: str,
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).execute(current_user, org_context, operation_id)
    await session.commit()
    return OperationView.model_validate(row)
