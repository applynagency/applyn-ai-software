"""Identity utility endpoints: machine-principal introspection and scope catalog."""

from __future__ import annotations

from fastapi import APIRouter

from app.auth.api_key_auth import ApiPrincipal
from app.auth.dependencies import CurrentUser
from app.schemas.identity import ScopeCatalogResponse
from app.services.identity import scopes as scope_lib

router = APIRouter(prefix="/identity", tags=["Identity"])


@router.get("/whoami")
async def whoami(principal: ApiPrincipal):
    """Resolve the principal behind an API key (org / personal / service account)."""
    return {
        "api_key_id": principal.api_key_id,
        "principal_type": principal.principal_type,
        "organization_id": principal.organization_id,
        "user_id": principal.user_id,
        "service_account_id": principal.service_account_id,
        "role": principal.role.value if principal.role else None,
        "scopes": principal.scopes,
    }


@router.get("/scopes", response_model=ScopeCatalogResponse)
async def list_scopes(current_user: CurrentUser):
    return ScopeCatalogResponse(scopes=scope_lib.SCOPE_CATALOG)
