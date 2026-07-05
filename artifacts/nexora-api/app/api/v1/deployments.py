from fastapi import APIRouter, Body, Query, Response, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.deployment import (
    DeploymentLogListResponse,
    DeploymentRollbackRequest,
    DeploymentRunListResponse,
    DeploymentRunResponse,
)
from app.services.deployment import DeploymentService

router = APIRouter(prefix="/deployments", tags=["Deployments"])


@router.get("", response_model=DeploymentRunListResponse)
async def list_deployments(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    service = DeploymentService(session)
    return await service.list_deployments(
        current_user, org_context, offset=offset, limit=limit
    )


@router.get("/{deployment_id}", response_model=DeploymentRunResponse)
async def get_deployment(
    deployment_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await DeploymentService(session).get_run(deployment_id, current_user, org_context)


@router.get("/{deployment_id}/logs", response_model=DeploymentLogListResponse)
async def get_deployment_logs(
    deployment_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
):
    service = DeploymentService(session)
    return await service.list_logs(
        deployment_id, current_user, org_context, offset=offset, limit=limit
    )


@router.post("/{deployment_id}/rollback", response_model=DeploymentRunResponse)
async def rollback_deployment(
    deployment_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    data: DeploymentRollbackRequest | None = Body(default=None),
):
    service = DeploymentService(session)
    deployment_target = (
        data.deployment_target.model_dump()
        if data and data.deployment_target
        else None
    )
    credential_id = data.credential_id if data else None
    return await service.rollback(
        deployment_id,
        current_user,
        org_context,
        deployment_target=deployment_target,
        credential_id=credential_id,
    )


@router.delete("/{deployment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deployment(
    deployment_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = DeploymentService(session)
    await service.delete_deployment(deployment_id, current_user, org_context)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
