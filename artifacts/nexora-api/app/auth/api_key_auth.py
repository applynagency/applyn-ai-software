"""Authenticate machine principals (API keys / service accounts).

Unlike ``get_current_user`` (which resolves a human ``User``), this dependency
returns an :class:`ApiKeyPrincipal` and accepts any kind of API key —
organization, personal or service-account. Use it for machine-to-machine
endpoints where the caller may not be a human user.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import bearer_scheme
from app.database.session import get_db
from app.services.identity.api_keys import ApiKeyError, ApiKeyPrincipal, ApiKeyService


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


async def get_api_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ApiKeyPrincipal:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return await ApiKeyService(session).authenticate(
            credentials.credentials, ip=_client_ip(request)
        )
    except ApiKeyError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


ApiPrincipal = Annotated[ApiKeyPrincipal, Depends(get_api_principal)]
