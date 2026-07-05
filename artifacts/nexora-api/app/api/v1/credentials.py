"""Sprint 35A — Infrastructure Credentials API.

Customers register and manage their own infrastructure credentials. Secrets are
encrypted at rest and are NEVER returned by any endpoint.
"""

from fastapi import APIRouter, Response, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.credential import (
    CredentialCreateRequest,
    CredentialListResponse,
    CredentialResponse,
    CredentialUpdateRequest,
    InfrastructureValidationResponse,
)
from app.security.secrets import SecretManagerService
from app.services.infrastructure import InfrastructureService

router = APIRouter(prefix="/credentials", tags=["Infrastructure Credentials"])


def _validation_response(credential, report) -> InfrastructureValidationResponse:
    return InfrastructureValidationResponse(
        credential_id=credential.id,
        provider=credential.provider,
        status=credential.status,
        readiness_score=report.score,
        ready=report.verified,
        checks=[c.as_dict() for c in report.checks],
        guidance=report.guidance,
        last_verified_at=credential.last_verified_at,
    )


@router.post("", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_credential(
    data: CredentialCreateRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = SecretManagerService(session)
    credential = await service.create_credential(
        provider=data.provider.value,
        name=data.name,
        secret={k: v for k, v in data.secret.items()},
        user=current_user,
        org_context=org_context,
    )
    return CredentialResponse.model_validate(credential)


@router.get("", response_model=CredentialListResponse)
async def list_credentials(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = SecretManagerService(session)
    items, total = await service.list_credentials(current_user, org_context)
    return CredentialListResponse(
        items=[CredentialResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get("/{credential_id}", response_model=CredentialResponse)
async def get_credential(
    credential_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = SecretManagerService(session)
    credential = await service.get_credential(credential_id, current_user, org_context)
    return CredentialResponse.model_validate(credential)


@router.put("/{credential_id}", response_model=CredentialResponse)
async def update_credential(
    credential_id: str,
    data: CredentialUpdateRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = SecretManagerService(session)
    credential = await service.update_credential(
        credential_id,
        name=data.name,
        secret=({k: v for k, v in data.secret.items()} if data.secret is not None else None),
        is_active=data.is_active,
        user=current_user,
        org_context=org_context,
    )
    return CredentialResponse.model_validate(credential)


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = SecretManagerService(session)
    await service.delete_credential(credential_id, current_user, org_context)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ----------------------- Sprint 35B: BYOI verification ---------------------- #
@router.post("/{credential_id}/verify", response_model=InfrastructureValidationResponse)
async def verify_credential(
    credential_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = InfrastructureService(session)
    credential, report = await service.verify(credential_id, current_user, org_context)
    return _validation_response(credential, report)


@router.get("/{credential_id}/status", response_model=CredentialResponse)
async def credential_status(
    credential_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = InfrastructureService(session)
    credential = await service.get_status(credential_id, current_user, org_context)
    return CredentialResponse.model_validate(credential)


@router.post("/{credential_id}/validate", response_model=InfrastructureValidationResponse)
async def validate_credential_for_deploy(
    credential_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = InfrastructureService(session)
    result = await service.validate_for_deploy(credential_id, current_user, org_context)
    return InfrastructureValidationResponse(
        credential_id=result["credential_id"],
        provider=result["provider"],
        status=result["status"],
        readiness_score=result["readiness_score"],
        ready=result["ready"],
        checks=result["checks"],
        guidance=result["guidance"],
    )
