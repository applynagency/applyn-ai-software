"""SCIM bearer-token authentication and admin token management.

Every SCIM request authenticates with ``Authorization: Bearer <token>``. The
token resolves to exactly one organization, so all SCIM operations are scoped to
that tenant. Tokens are stored only as SHA-256 hashes; the plaintext is returned
once at creation.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.base import utcnow
from app.models.scim import ScimToken
from app.repositories.scim import ScimTokenRepository
from app.services.scim.errors import ScimError

_TOKEN_PREFIX = "scim_"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_token() -> tuple[str, str, str]:
    """Return ``(plaintext, hashed, display_prefix)`` for a new SCIM token."""
    plaintext = _TOKEN_PREFIX + secrets.token_urlsafe(32)
    return plaintext, hash_token(plaintext), plaintext[:12]


@dataclass
class ScimContext:
    organization_id: str
    token_id: str
    session: AsyncSession


async def authenticate(request, session: AsyncSession) -> ScimContext:
    if not settings.SCIM_ENABLED:
        raise ScimError(404, "SCIM is not enabled")
    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("bearer "):
        raise ScimError(401, "Missing or malformed bearer token")
    token = header[7:].strip()
    if not token:
        raise ScimError(401, "Missing bearer token")

    repo = ScimTokenRepository(session)
    record = await repo.get_by_hash(hash_token(token))
    if record is None or not record.active:
        raise ScimError(401, "Invalid or revoked SCIM token")

    record.last_used_at = utcnow()
    session.add(record)
    await session.flush()
    return ScimContext(
        organization_id=record.organization_id, token_id=record.id, session=session
    )


# --- admin token management (superuser) -------------------------------------


async def create_token(
    session: AsyncSession, *, organization_id: str, name: str, created_by: str | None
) -> tuple[ScimToken, str]:
    plaintext, hashed, prefix = generate_token()
    repo = ScimTokenRepository(session)
    token = await repo.create(
        organization_id=organization_id,
        name=name,
        hashed_token=hashed,
        token_prefix=prefix,
        active=True,
        created_by=created_by,
    )
    return token, plaintext


async def list_tokens(session: AsyncSession, organization_id: str) -> list[ScimToken]:
    return await ScimTokenRepository(session).list_for_organization(organization_id)


async def revoke_token(session: AsyncSession, token_id: str) -> bool:
    repo = ScimTokenRepository(session)
    token = await repo.get_by_id(token_id)
    if token is None:
        return False
    await repo.update(token, active=False)
    return True
