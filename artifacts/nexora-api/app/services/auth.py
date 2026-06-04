from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, verify_token
from app.core.config import settings
from app.core.exceptions import ConflictError, UnauthorizedError
from app.repositories.user import UserRepository
from app.repositories.audit import AuditLogRepository
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserResponse
from app.models.user import User
from app.core.logging import get_logger

logger = get_logger(__name__)


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.audit_repo = AuditLogRepository(session)

    async def register(self, data: RegisterRequest, ip: str = "") -> UserResponse:
        existing_email = await self.user_repo.get_by_email(data.email)
        if existing_email:
            raise ConflictError("Email is already registered")

        existing_username = await self.user_repo.get_by_username(data.username)
        if existing_username:
            raise ConflictError("Username is already taken")

        user = await self.user_repo.create(
            email=data.email,
            username=data.username,
            full_name=data.full_name,
            hashed_password=hash_password(data.password),
        )

        await self.audit_repo.log(
            action="user.register",
            resource_type="user",
            resource_id=user.id,
            user_id=user.id,
            details={"email": user.email},
            ip_address=ip,
        )

        logger.info("user_registered", user_id=user.id, email=user.email)
        return UserResponse.model_validate(user)

    async def login(self, data: LoginRequest, ip: str = "") -> TokenResponse:
        user = await self.user_repo.get_by_email(data.email)
        if not user or not verify_password(data.password, user.hashed_password):
            raise UnauthorizedError("Invalid email or password")

        if not user.is_active:
            raise UnauthorizedError("Account is deactivated")

        access_token = create_access_token(subject=user.id)
        refresh_token = create_refresh_token(subject=user.id)

        await self.user_repo.update_refresh_token(user, refresh_token)

        await self.audit_repo.log(
            action="user.login",
            resource_type="user",
            resource_id=user.id,
            user_id=user.id,
            ip_address=ip,
        )

        logger.info("user_login", user_id=user.id)
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh(self, refresh_token: str) -> TokenResponse:
        user_id = verify_token(refresh_token, token_type="refresh")
        if not user_id:
            raise UnauthorizedError("Invalid or expired refresh token")

        user = await self.user_repo.get_by_id(user_id)
        if not user or user.refresh_token != refresh_token:
            raise UnauthorizedError("Refresh token has been revoked")

        new_access_token = create_access_token(subject=user.id)
        new_refresh_token = create_refresh_token(subject=user.id)

        await self.user_repo.update_refresh_token(user, new_refresh_token)

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def logout(self, user: User) -> None:
        await self.user_repo.update_refresh_token(user, None)
        await self.audit_repo.log(
            action="user.logout",
            resource_type="user",
            resource_id=user.id,
            user_id=user.id,
        )
        logger.info("user_logout", user_id=user.id)
