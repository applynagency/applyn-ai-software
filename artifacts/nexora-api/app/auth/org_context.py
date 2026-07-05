from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from app.auth.dependencies import DBSession, bearer_scheme, get_current_user
from app.core.security import decode_token
from app.models.organization import OrganizationRole
from app.models.user import User
from app.repositories.organization import OrganizationMemberRepository


@dataclass
class OrgContext:
    user: User
    organization_id: str | None
    role: OrganizationRole | None

    @property
    def requires_organization(self) -> str:
        if not self.organization_id or not self.role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization context required. Switch or create an organization.",
            )
        return self.organization_id


async def get_org_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    current_user: Annotated[User, Depends(get_current_user)],
    session: DBSession,
) -> OrgContext:
    organization_id: str | None = None
    role: OrganizationRole | None = None

    if credentials:
        payload = decode_token(credentials.credentials)
        if payload.get("type") == "access":
            org_id = payload.get("organization_id")
            if org_id:
                organization_id = str(org_id)
                if current_user.is_superuser:
                    role_value = payload.get("role")
                    if role_value:
                        try:
                            role = OrganizationRole(str(role_value))
                        except ValueError:
                            role = None
                else:
                    member_repo = OrganizationMemberRepository(session)
                    membership = await member_repo.get_membership(
                        organization_id, current_user.id
                    )
                    if not membership:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Organization membership is no longer valid",
                            headers={"WWW-Authenticate": "Bearer"},
                        )
                    role = membership.role

    return OrgContext(
        user=current_user,
        organization_id=organization_id,
        role=role,
    )


OrgContextDep = Annotated[OrgContext, Depends(get_org_context)]
