from fastapi import APIRouter, Request
from app.auth.dependencies import CurrentUser, DBSession
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, RefreshTokenRequest, UserResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(data: RegisterRequest, request: Request, session: DBSession):
    service = AuthService(session)
    return await service.register(data, ip=_get_client_ip(request))


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, request: Request, session: DBSession):
    service = AuthService(session)
    return await service.login(data, ip=_get_client_ip(request))


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshTokenRequest, session: DBSession):
    service = AuthService(session)
    return await service.refresh(data.refresh_token)


@router.post("/logout", status_code=204)
async def logout(current_user: CurrentUser, session: DBSession):
    service = AuthService(session)
    await service.logout(current_user)


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser):
    return UserResponse.model_validate(current_user)
