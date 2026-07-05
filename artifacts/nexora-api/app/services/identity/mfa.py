"""Multi-factor authentication: TOTP enrollment, verification and recovery codes."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.base import utcnow
from app.models.identity import MfaRecoveryCode, UserMfaTotp
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.security.secrets import get_cipher
from app.services.identity import totp as totp_lib

_RECOVERY_CODE_COUNT = 10


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().replace("-", "").encode("utf-8")).hexdigest()


def _generate_recovery_codes(count: int = _RECOVERY_CODE_COUNT) -> list[str]:
    codes: list[str] = []
    for _ in range(count):
        raw = secrets.token_hex(5)  # 10 hex chars
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes


class MfaError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class EnrollmentResult:
    secret: str
    otpauth_uri: str


class MfaService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditLogRepository(session)

    async def _get_totp(self, user_id: str) -> UserMfaTotp | None:
        return await self.session.scalar(
            select(UserMfaTotp).where(UserMfaTotp.user_id == user_id)
        )

    async def is_enrolled(self, user_id: str) -> bool:
        row = await self._get_totp(user_id)
        return bool(row and row.confirmed)

    async def begin_enrollment(self, user: User) -> EnrollmentResult:
        existing = await self._get_totp(user.id)
        if existing and existing.confirmed:
            raise MfaError("MFA is already enabled; reset it first", 409)

        secret = totp_lib.generate_secret()
        encrypted = get_cipher().encrypt(secret)
        if existing:
            existing.encrypted_secret = encrypted
            existing.confirmed = False
            existing.confirmed_at = None
            self.session.add(existing)
        else:
            self.session.add(
                UserMfaTotp(user_id=user.id, encrypted_secret=encrypted, confirmed=False)
            )
        await self.session.flush()

        uri = totp_lib.provisioning_uri(
            secret,
            account_name=user.email,
            issuer=settings.MFA_ISSUER,
        )
        return EnrollmentResult(secret=secret, otpauth_uri=uri)

    async def confirm_enrollment(self, user: User, code: str) -> list[str]:
        """Verify the first code, activate MFA and return fresh recovery codes."""
        row = await self._get_totp(user.id)
        if row is None:
            raise MfaError("No pending MFA enrollment; start enrollment first", 409)
        if row.confirmed:
            raise MfaError("MFA is already enabled", 409)
        secret = get_cipher().decrypt(row.encrypted_secret)
        if not totp_lib.verify_totp(secret, code):
            raise MfaError("Invalid verification code", 400)

        row.confirmed = True
        row.confirmed_at = utcnow()
        row.last_used_at = utcnow()
        self.session.add(row)
        recovery = await self._reset_recovery_codes(user.id)
        await self.session.flush()
        await self.audit.log(
            action="mfa.enabled",
            resource_type="user",
            resource_id=user.id,
            user_id=user.id,
        )
        return recovery

    async def verify(self, user_id: str, code: str) -> bool:
        """Verify a TOTP code or consume a recovery code."""
        row = await self._get_totp(user_id)
        if row is None or not row.confirmed:
            return False
        secret = get_cipher().decrypt(row.encrypted_secret)
        if totp_lib.verify_totp(secret, code):
            row.last_used_at = utcnow()
            self.session.add(row)
            await self.session.flush()
            return True
        return await self._consume_recovery_code(user_id, code)

    async def _consume_recovery_code(self, user_id: str, code: str) -> bool:
        code_hash = _hash_code(code)
        rc = await self.session.scalar(
            select(MfaRecoveryCode).where(
                MfaRecoveryCode.user_id == user_id,
                MfaRecoveryCode.code_hash == code_hash,
                MfaRecoveryCode.used_at.is_(None),
            )
        )
        if rc is None:
            return False
        rc.used_at = utcnow()
        self.session.add(rc)
        await self.session.flush()
        await self.audit.log(
            action="mfa.recovery_code_used",
            resource_type="user",
            resource_id=user_id,
            user_id=user_id,
        )
        return True

    async def _reset_recovery_codes(self, user_id: str) -> list[str]:
        # Delete existing codes, then mint a fresh set.
        existing = await self.session.scalars(
            select(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user_id)
        )
        for rc in existing.all():
            await self.session.delete(rc)
        codes = _generate_recovery_codes()
        for code in codes:
            self.session.add(
                MfaRecoveryCode(user_id=user_id, code_hash=_hash_code(code))
            )
        await self.session.flush()
        return codes

    async def regenerate_recovery_codes(self, user: User) -> list[str]:
        if not await self.is_enrolled(user.id):
            raise MfaError("MFA is not enabled", 409)
        codes = await self._reset_recovery_codes(user.id)
        await self.audit.log(
            action="mfa.recovery_codes_regenerated",
            resource_type="user",
            resource_id=user.id,
            user_id=user.id,
        )
        return codes

    async def remaining_recovery_codes(self, user_id: str) -> int:
        rows = await self.session.scalars(
            select(MfaRecoveryCode).where(
                MfaRecoveryCode.user_id == user_id,
                MfaRecoveryCode.used_at.is_(None),
            )
        )
        return len(rows.all())

    async def disable(self, user: User, *, actor_user_id: str | None = None) -> None:
        row = await self._get_totp(user.id)
        if row is not None:
            await self.session.delete(row)
        existing = await self.session.scalars(
            select(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id)
        )
        for rc in existing.all():
            await self.session.delete(rc)
        await self.session.flush()
        await self.audit.log(
            action="mfa.disabled",
            resource_type="user",
            resource_id=user.id,
            user_id=actor_user_id or user.id,
        )
