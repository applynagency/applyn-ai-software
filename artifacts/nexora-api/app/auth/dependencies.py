from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import credentials_exception
from app.core.security import decode_token
from app.database.session import get_db
from app.models.user import User
from app.repositories.user import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


API_KEY_TOKEN_PREFIX = "nxk_"


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if not credentials:
        raise credentials_exception

    token = credentials.credentials

    # Personal API keys authenticate as their owning user on any user endpoint.
    if token.startswith(API_KEY_TOKEN_PREFIX):
        return await _user_from_api_key(token, session)

    try:
        payload = decode_token(token)
    except JWTError:
        raise credentials_exception from None
    if payload.get("type") != "access":
        raise credentials_exception
    user_id = payload.get("sub")
    if not user_id:
        raise credentials_exception

    # Reject tokens that have been revoked server-side (logout / revoke session).
    if settings.JWT_DENYLIST_ENABLED:
        from app.redis import denylist

        if await denylist.is_revoked(payload.get("jti", "")):
            raise credentials_exception

    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    return user


async def _user_from_api_key(token: str, session: AsyncSession) -> User:
    from app.models.identity import ApiKeyPrincipalType
    from app.services.identity.api_keys import ApiKeyError, ApiKeyService

    try:
        principal = await ApiKeyService(session).authenticate(token)
    except ApiKeyError:
        raise credentials_exception from None
    if (
        principal.principal_type != ApiKeyPrincipalType.USER.value
        or not principal.user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This API key cannot be used for interactive user access",
        )
    user = await UserRepository(session).get_by_id(principal.user_id)
    if not user:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated"
        )
    return user


async def get_current_superuser(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser access required",
        )
    return current_user


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentSuperuser = Annotated[User, Depends(get_current_superuser)]
DBSession = Annotated[AsyncSession, Depends(get_db)]
