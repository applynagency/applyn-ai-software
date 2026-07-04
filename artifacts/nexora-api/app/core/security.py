import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    expire = datetime.now(UTC) + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(UTC),
        "jti": uuid.uuid4().hex,
        "type": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    expire = datetime.now(UTC) + timedelta(
        days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(UTC),
        "jti": uuid.uuid4().hex,
        "type": "refresh",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def _signing_keys() -> list[str]:
    """Active signing key first, then any retired keys accepted for verification.

    Supports zero-downtime secret rotation: rotate ``JWT_SECRET_KEY`` to a new
    value and move the previous one into ``JWT_SECRET_KEYS_RETIRED`` (comma
    separated). Newly issued tokens use the active key; tokens signed with a
    retired key keep verifying until they expire, after which the retired key can
    be dropped.
    """
    keys = [settings.JWT_SECRET_KEY]
    retired = (getattr(settings, "JWT_SECRET_KEYS_RETIRED", "") or "").strip()
    if retired:
        keys.extend(k.strip() for k in retired.split(",") if k.strip())
    return keys


def decode_token(token: str) -> dict[str, Any]:
    keys = _signing_keys()
    last_error: JWTError | None = None
    for key in keys:
        try:
            return jwt.decode(token, key, algorithms=[settings.JWT_ALGORITHM])
        except JWTError as exc:  # try the next (retired) key
            last_error = exc
    # Preserve the original failure semantics for callers catching JWTError.
    raise last_error if last_error is not None else JWTError("token verification failed")


def verify_token(token: str, token_type: str = "access") -> str | None:
    try:
        payload = decode_token(token)
        if payload.get("type") != token_type:
            return None
        subject: str = payload.get("sub", "")
        return subject if subject else None
    except JWTError:
        return None


def token_remaining_seconds(payload: dict[str, Any]) -> int:
    """Seconds until ``payload`` expires (>= 1), for denylist TTLs."""
    exp = payload.get("exp")
    if exp is None:
        return settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    try:
        remaining = int(exp) - int(datetime.now(UTC).timestamp())
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    return max(1, remaining)
