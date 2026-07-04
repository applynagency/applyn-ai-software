from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError

from app.auth.dependencies import CurrentUser, DBSession, bearer_scheme
from app.core.security import decode_token
from app.schemas.auth import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    SessionListResponse,
    TokenResponse,
    UserResponse,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])

BearerCreds = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def _payload_from(credentials: HTTPAuthorizationCredentials | None) -> dict | None:
    if not credentials:
        return None
    try:
        return decode_token(credentials.credentials)
    except JWTError:
        return None


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(data: RegisterRequest, request: Request, session: DBSession):
    service = AuthService(session)
    return await service.register(data, ip=_get_client_ip(request))


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, request: Request, session: DBSession):
    service = AuthService(session)
    return await service.login(
        data,
        ip=_get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshTokenRequest, session: DBSession):
    service = AuthService(session)
    return await service.refresh(data.refresh_token, organization_id=data.organization_id)


@router.post("/logout", status_code=204)
async def logout(current_user: CurrentUser, session: DBSession, credentials: BearerCreds):
    service = AuthService(session)
    await service.logout(current_user, access_payload=_payload_from(credentials))


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser):
    return UserResponse.model_validate(current_user)


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    current_user: CurrentUser, session: DBSession, credentials: BearerCreds
):
    service = AuthService(session)
    payload = _payload_from(credentials) or {}
    current_jti = payload.get("jti")
    items = await service.list_sessions(current_user)
    return SessionListResponse(
        sessions=[{**s, "current": s.get("jti") == current_jti} for s in items],
        total=len(items),
    )


@router.delete("/sessions/{jti}", status_code=204)
async def revoke_session(jti: str, current_user: CurrentUser, session: DBSession):
    service = AuthService(session)
    await service.revoke_session(current_user, jti)


@router.post("/sessions/revoke-others", status_code=200)
async def revoke_other_sessions(
    current_user: CurrentUser, session: DBSession, credentials: BearerCreds
):
    service = AuthService(session)
    payload = _payload_from(credentials) or {}
    revoked = await service.revoke_other_sessions(current_user, payload.get("jti"))
    return {"revoked": revoked}
