import re

from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    full_name: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_-]{3,50}$", v):
            raise ValueError("Username must be 3-50 characters: letters, numbers, _ or -")
        return v.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    # Required when the account has MFA enabled (TOTP code or recovery code).
    mfa_code: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    organization_id: str | None = None
    role: str | None = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str
    organization_id: str | None = None


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: str
    is_active: bool
    is_superuser: bool

    model_config = {"from_attributes": True}


class SessionInfo(BaseModel):
    jti: str
    user_id: str
    ip: str | None = None
    user_agent: str | None = None
    organization_id: str | None = None
    created_at: float | None = None
    expires_at: float | None = None
    current: bool = False


class SessionListResponse(BaseModel):
    sessions: list[SessionInfo]
    total: int
