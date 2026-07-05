"""Organization security policy configuration (admin scoped)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.auth.dependencies import DBSession
from app.auth.org_context import OrgContext, OrgContextDep
from app.models.organization import OrganizationRole
from app.schemas.identity import SecurityPolicyResponse, SecurityPolicyUpdate
from app.services.identity.security_policy import PolicyViolation, SecurityPolicyService

router = APIRouter(prefix="/security-policy", tags=["Security Policy"])

_ADMIN_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN}


def _require_org_admin(ctx: OrgContext) -> str:
    org_id = ctx.requires_organization
    if not (ctx.user.is_superuser or ctx.role in _ADMIN_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization admin role required",
        )
    return org_id


@router.get("", response_model=SecurityPolicyResponse)
async def get_security_policy(ctx: OrgContextDep, session: DBSession):
    org_id = _require_org_admin(ctx)
    policy = await SecurityPolicyService(session).get_or_create(org_id)
    await session.commit()
    return SecurityPolicyResponse.model_validate(policy)


@router.put("", response_model=SecurityPolicyResponse)
async def update_security_policy(
    payload: SecurityPolicyUpdate, ctx: OrgContextDep, session: DBSession
):
    org_id = _require_org_admin(ctx)
    try:
        policy = await SecurityPolicyService(session).update(
            org_id,
            payload.model_dump(exclude_unset=True),
            actor_user_id=ctx.user.id,
        )
    except PolicyViolation as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    await session.commit()
    return SecurityPolicyResponse.model_validate(policy)
