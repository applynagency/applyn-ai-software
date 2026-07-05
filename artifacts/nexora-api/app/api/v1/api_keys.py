"""API key management — personal keys (per user) and organization keys."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContext, OrgContextDep
from app.models.identity import ApiKeyPrincipalType
from app.models.organization import OrganizationRole
from app.schemas.identity import (
    ApiKeyCreate,
    ApiKeyListResponse,
    ApiKeyResponse,
    ApiKeyWithSecret,
    PersonalApiKeyCreate,
)
from app.services.identity.api_keys import ApiKeyError, ApiKeyService
from app.services.identity.security_policy import SecurityPolicyService

router = APIRouter(prefix="/api-keys", tags=["API Keys"])

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


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


# --- personal keys -----------------------------------------------------------


@router.post(
    "/personal", response_model=ApiKeyWithSecret, status_code=status.HTTP_201_CREATED
)
async def create_personal_key(
    payload: PersonalApiKeyCreate, current_user: CurrentUser, session: DBSession
):
    service = ApiKeyService(session)
    try:
        key, plaintext = await service.create(
            principal_type=ApiKeyPrincipalType.USER,
            name=payload.name,
            scopes=payload.scopes,
            user_id=current_user.id,
            expires_at=payload.expires_at,
            created_by=current_user.id,
            actor_user_id=current_user.id,
        )
    except ApiKeyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    await session.commit()
    return _with_secret(key, plaintext)


@router.get("/personal", response_model=ApiKeyListResponse)
async def list_personal_keys(current_user: CurrentUser, session: DBSession):
    keys = await ApiKeyService(session).list(user_id=current_user.id)
    return ApiKeyListResponse(
        items=[ApiKeyResponse.model_validate(k) for k in keys], total=len(keys)
    )


@router.delete("/personal/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_personal_key(
    key_id: str, current_user: CurrentUser, session: DBSession
):
    service = ApiKeyService(session)
    key = await service.get(key_id)
    if key is None or key.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="API key not found")
    await service.revoke(key, actor_user_id=current_user.id)
    await session.commit()


@router.post("/personal/{key_id}/rotate", response_model=ApiKeyWithSecret)
async def rotate_personal_key(
    key_id: str, current_user: CurrentUser, session: DBSession
):
    service = ApiKeyService(session)
    key = await service.get(key_id)
    if key is None or key.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="API key not found")
    new_key, plaintext = await service.rotate(key, actor_user_id=current_user.id)
    await session.commit()
    return _with_secret(new_key, plaintext)


# --- organization keys -------------------------------------------------------


async def _ensure_api_keys_enabled(session, org_id: str) -> None:
    policy = await SecurityPolicyService(session).get(org_id)
    if policy is not None and not policy.api_keys_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API keys are disabled by the organization security policy",
        )


@router.post(
    "/organization", response_model=ApiKeyWithSecret, status_code=status.HTTP_201_CREATED
)
async def create_org_key(
    payload: ApiKeyCreate, ctx: OrgContextDep, session: DBSession
):
    org_id = _require_org_admin(ctx)
    await _ensure_api_keys_enabled(session, org_id)
    service = ApiKeyService(session)
    try:
        key, plaintext = await service.create(
            principal_type=ApiKeyPrincipalType.ORGANIZATION,
            name=payload.name,
            scopes=payload.scopes,
            organization_id=org_id,
            expires_at=payload.expires_at,
            created_by=ctx.user.id,
            actor_user_id=ctx.user.id,
        )
    except ApiKeyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    await session.commit()
    return _with_secret(key, plaintext)


@router.get("/organization", response_model=ApiKeyListResponse)
async def list_org_keys(ctx: OrgContextDep, session: DBSession):
    org_id = _require_org_admin(ctx)
    keys = await ApiKeyService(session).list(organization_id=org_id)
    return ApiKeyListResponse(
        items=[ApiKeyResponse.model_validate(k) for k in keys], total=len(keys)
    )


@router.delete("/organization/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_org_key(key_id: str, ctx: OrgContextDep, session: DBSession):
    org_id = _require_org_admin(ctx)
    service = ApiKeyService(session)
    key = await service.get(key_id)
    if key is None or key.organization_id != org_id or key.user_id is not None:
        raise HTTPException(status_code=404, detail="API key not found")
    await service.revoke(key, actor_user_id=ctx.user.id)
    await session.commit()


@router.post("/organization/{key_id}/rotate", response_model=ApiKeyWithSecret)
async def rotate_org_key(key_id: str, ctx: OrgContextDep, session: DBSession):
    org_id = _require_org_admin(ctx)
    service = ApiKeyService(session)
    key = await service.get(key_id)
    if key is None or key.organization_id != org_id or key.user_id is not None:
        raise HTTPException(status_code=404, detail="API key not found")
    new_key, plaintext = await service.rotate(key, actor_user_id=ctx.user.id)
    await session.commit()
    return _with_secret(new_key, plaintext)
