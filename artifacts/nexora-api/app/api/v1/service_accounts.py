"""Service account management (organization-admin scoped)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.auth.dependencies import DBSession
from app.auth.org_context import OrgContext, OrgContextDep
from app.models.organization import OrganizationRole
from app.schemas.identity import (
    ApiKeyCreate,
    ApiKeyListResponse,
    ApiKeyResponse,
    ApiKeyWithSecret,
    ServiceAccountCreate,
    ServiceAccountListResponse,
    ServiceAccountResponse,
    ServiceAccountUpdate,
)
from app.services.identity.api_keys import ApiKeyError
from app.services.identity.service_accounts import ServiceAccountService

router = APIRouter(prefix="/service-accounts", tags=["Service Accounts"])

_ADMIN_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN}


def _require_org_admin(ctx: OrgContext) -> str:
    org_id = ctx.requires_organization
    if not (ctx.user.is_superuser or ctx.role in _ADMIN_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization admin role required",
        )
    return org_id


def _with_secret(key, plaintext: str) -> ApiKeyWithSecret:
    return ApiKeyWithSecret(
        **ApiKeyResponse.model_validate(key).model_dump(), api_key=plaintext
    )


@router.post("", response_model=ServiceAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_service_account(
    payload: ServiceAccountCreate, ctx: OrgContextDep, session: DBSession
):
    org_id = _require_org_admin(ctx)
    service = ServiceAccountService(session)
    try:
        sa = await service.create(
            organization_id=org_id,
            name=payload.name,
            description=payload.description,
            role=payload.role,
            scopes=payload.scopes,
            expires_at=payload.expires_at,
            actor_user_id=ctx.user.id,
        )
    except (ApiKeyError, ValueError) as exc:
        code = getattr(exc, "status_code", 400)
        raise HTTPException(status_code=code, detail=str(exc)) from None
    await session.commit()
    return ServiceAccountResponse.model_validate(sa)


@router.get("", response_model=ServiceAccountListResponse)
async def list_service_accounts(ctx: OrgContextDep, session: DBSession):
    org_id = _require_org_admin(ctx)
    accounts = await ServiceAccountService(session).list(org_id)
    return ServiceAccountListResponse(
        items=[ServiceAccountResponse.model_validate(a) for a in accounts],
        total=len(accounts),
    )


@router.get("/{sa_id}", response_model=ServiceAccountResponse)
async def get_service_account(sa_id: str, ctx: OrgContextDep, session: DBSession):
    org_id = _require_org_admin(ctx)
    sa = await ServiceAccountService(session).get(org_id, sa_id)
    if sa is None:
        raise HTTPException(status_code=404, detail="Service account not found")
    return ServiceAccountResponse.model_validate(sa)


@router.patch("/{sa_id}", response_model=ServiceAccountResponse)
async def update_service_account(
    sa_id: str, payload: ServiceAccountUpdate, ctx: OrgContextDep, session: DBSession
):
    org_id = _require_org_admin(ctx)
    service = ServiceAccountService(session)
    sa = await service.get(org_id, sa_id)
    if sa is None:
        raise HTTPException(status_code=404, detail="Service account not found")
    sa = await service.update(
        sa,
        description=payload.description,
        role=payload.role,
        scopes=payload.scopes,
        disabled=payload.disabled,
        expires_at=payload.expires_at,
        clear_expiry=payload.clear_expiry,
        actor_user_id=ctx.user.id,
    )
    await session.commit()
    return ServiceAccountResponse.model_validate(sa)


@router.post("/{sa_id}/disable", response_model=ServiceAccountResponse)
async def disable_service_account(sa_id: str, ctx: OrgContextDep, session: DBSession):
    org_id = _require_org_admin(ctx)
    service = ServiceAccountService(session)
    sa = await service.get(org_id, sa_id)
    if sa is None:
        raise HTTPException(status_code=404, detail="Service account not found")
    sa = await service.disable(sa, actor_user_id=ctx.user.id)
    await session.commit()
    return ServiceAccountResponse.model_validate(sa)


@router.post(
    "/{sa_id}/keys", response_model=ApiKeyWithSecret, status_code=status.HTTP_201_CREATED
)
async def issue_service_account_key(
    sa_id: str, payload: ApiKeyCreate, ctx: OrgContextDep, session: DBSession
):
    org_id = _require_org_admin(ctx)
    service = ServiceAccountService(session)
    sa = await service.get(org_id, sa_id)
    if sa is None:
        raise HTTPException(status_code=404, detail="Service account not found")
    try:
        key, plaintext = await service.issue_key(
            sa,
            name=payload.name,
            scopes=payload.scopes,
            expires_at=payload.expires_at,
            actor_user_id=ctx.user.id,
        )
    except ApiKeyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    await session.commit()
    return _with_secret(key, plaintext)


@router.get("/{sa_id}/keys", response_model=ApiKeyListResponse)
async def list_service_account_keys(
    sa_id: str, ctx: OrgContextDep, session: DBSession
):
    org_id = _require_org_admin(ctx)
    service = ServiceAccountService(session)
    sa = await service.get(org_id, sa_id)
    if sa is None:
        raise HTTPException(status_code=404, detail="Service account not found")
    keys = await service.list_keys(sa)
    return ApiKeyListResponse(
        items=[ApiKeyResponse.model_validate(k) for k in keys], total=len(keys)
    )


@router.delete(
    "/{sa_id}/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def revoke_service_account_key(
    sa_id: str, key_id: str, ctx: OrgContextDep, session: DBSession
):
    org_id = _require_org_admin(ctx)
    sa_service = ServiceAccountService(session)
    sa = await sa_service.get(org_id, sa_id)
    if sa is None:
        raise HTTPException(status_code=404, detail="Service account not found")
    key = await sa_service.keys.get(key_id)
    if key is None or key.service_account_id != sa.id:
        raise HTTPException(status_code=404, detail="API key not found")
    await sa_service.keys.revoke(key, actor_user_id=ctx.user.id)
    await session.commit()
