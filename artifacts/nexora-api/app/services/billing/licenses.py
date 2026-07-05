"""License engine (Sprint 61C).

Issues and validates licenses for SaaS, on-prem, offline and enterprise-contract
scenarios. Validation is HMAC-signature based and **independent of Stripe / any
billing provider** so it works fully offline / air-gapped.

An offline license token is ``base64(payload_json).hex(hmac_sha256(payload))`` —
self-contained and verifiable without a database.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.billing import License, LicenseStatus, LicenseType
from app.repositories.audit import AuditLogRepository


def _now() -> datetime:
    return datetime.now(UTC)


def _signing_key() -> bytes:
    key = settings.LICENSE_SIGNING_KEY or settings.JWT_SECRET_KEY or "nexora-dev-license-key"
    return key.encode("utf-8")


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_payload(payload: dict) -> str:
    return hmac.new(_signing_key(), _canonical(payload), hashlib.sha256).hexdigest()


def verify_signature(payload: dict, signature: str) -> bool:
    expected = sign_payload(payload)
    return hmac.compare_digest(expected, signature or "")


def encode_offline_token(payload: dict) -> str:
    raw = _canonical(payload)
    b64 = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return f"{b64}.{sign_payload(payload)}"


def decode_offline_token(token: str) -> dict | None:
    """Verify + decode an offline token. Returns the payload or None if invalid."""
    try:
        b64, signature = token.rsplit(".", 1)
        padded = b64 + "=" * (-len(b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except Exception:
        return None
    if not verify_signature(payload, signature):
        return None
    return payload


class LicenseError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class LicenseService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditLogRepository(session)

    async def issue(
        self, *, organization_id: str | None, license_type: LicenseType,
        plan_slug: str | None = None, seats: int = 0,
        features: dict | None = None, limits: dict | None = None,
        expires_at: datetime | None = None, actor_user_id: str | None = None,
    ) -> tuple[License, str]:
        now = _now()
        key = f"NX-{secrets.token_hex(16).upper()}"
        payload = {
            "license_key": key,
            "organization_id": organization_id,
            "license_type": license_type.value,
            "plan_slug": plan_slug,
            "seats": seats,
            "features": features or {},
            "limits": limits or {},
            "issued_at": now.isoformat(),
            "expires_at": expires_at.isoformat() if expires_at else None,
        }
        signature = sign_payload(payload)
        lic = License(
            organization_id=organization_id, license_key=key,
            license_type=license_type.value, status=LicenseStatus.ACTIVE.value,
            plan_slug=plan_slug, seats=seats, features=features or {}, limits=limits or {},
            issued_at=now, expires_at=expires_at, signature=signature,
            issued_by=actor_user_id,
        )
        self.session.add(lic)
        await self.session.flush()
        await self.audit.log(
            action="license.issued", resource_type="license", resource_id=lic.id,
            organization_id=organization_id, user_id=actor_user_id,
            details={"type": license_type.value, "plan": plan_slug, "seats": seats},
        )
        token = encode_offline_token(payload)
        return lic, token

    async def get_by_key(self, license_key: str) -> License | None:
        return await self.session.scalar(
            select(License).where(License.license_key == license_key)
        )

    async def active_for_org(self, organization_id: str) -> License | None:
        rows = (await self.session.execute(
            select(License).where(
                License.organization_id == organization_id,
                License.status == LicenseStatus.ACTIVE.value,
            ).order_by(License.created_at.desc())
        )).scalars().all()
        for lic in rows:
            if self._is_valid(lic):
                return lic
        return None

    def _is_valid(self, lic: License) -> bool:
        if lic.status != LicenseStatus.ACTIVE.value:
            return False
        if lic.expires_at is not None:
            exp = lic.expires_at if lic.expires_at.tzinfo else lic.expires_at.replace(tzinfo=UTC)
            if exp <= _now():
                return False
        # Re-verify the stored signature (tamper detection), if present.
        if lic.signature:
            payload = {
                "license_key": lic.license_key,
                "organization_id": lic.organization_id,
                "license_type": lic.license_type,
                "plan_slug": lic.plan_slug,
                "seats": lic.seats,
                "features": lic.features or {},
                "limits": lic.limits or {},
                "issued_at": lic.issued_at.isoformat() if lic.issued_at else None,
                "expires_at": lic.expires_at.isoformat() if lic.expires_at else None,
            }
            if not verify_signature(payload, lic.signature):
                return False
        return True

    async def validate(self, license_key: str) -> dict:
        """Validate a stored license by key. Does not touch any billing provider."""
        lic = await self.get_by_key(license_key)
        if lic is None:
            return {"valid": False, "reason": "not_found"}
        valid = self._is_valid(lic)
        return {
            "valid": valid,
            "reason": None if valid else "expired_or_revoked_or_tampered",
            "license_type": lic.license_type,
            "plan_slug": lic.plan_slug,
            "seats": lic.seats,
            "expires_at": lic.expires_at.isoformat() if lic.expires_at else None,
        }

    def validate_offline(self, token: str) -> dict:
        """Validate a self-contained offline token without any DB/provider."""
        payload = decode_offline_token(token)
        if payload is None:
            return {"valid": False, "reason": "bad_signature"}
        exp = payload.get("expires_at")
        if exp:
            try:
                expires = datetime.fromisoformat(exp)
                if (expires if expires.tzinfo else expires.replace(tzinfo=UTC)) <= _now():
                    return {"valid": False, "reason": "expired", **payload}
            except ValueError:
                return {"valid": False, "reason": "bad_expiry"}
        return {"valid": True, "reason": None, **payload}

    async def revoke(self, license_key: str, *, actor_user_id: str | None = None) -> License:
        lic = await self.get_by_key(license_key)
        if lic is None:
            raise LicenseError("License not found", status_code=404)
        lic.status = LicenseStatus.REVOKED.value
        self.session.add(lic)
        await self.session.flush()
        await self.audit.log(
            action="license.revoked", resource_type="license", resource_id=lic.id,
            organization_id=lic.organization_id, user_id=actor_user_id,
            details={"license_key": license_key},
        )
        return lic

    async def expire_due(self) -> int:
        """Mark active licenses past their expiry as EXPIRED; emit events."""
        now = _now()
        rows = (await self.session.execute(
            select(License).where(License.status == LicenseStatus.ACTIVE.value)
        )).scalars().all()
        expired = 0
        for lic in rows:
            if lic.expires_at is None:
                continue
            exp = lic.expires_at if lic.expires_at.tzinfo else lic.expires_at.replace(tzinfo=UTC)
            if exp <= now:
                lic.status = LicenseStatus.EXPIRED.value
                self.session.add(lic)
                expired += 1
                await self.audit.log(
                    action="license.expired", resource_type="license", resource_id=lic.id,
                    organization_id=lic.organization_id,
                    details={"license_key": lic.license_key},
                )
                if lic.organization_id:
                    from app.services.billing.webhooks import BillingWebhookService

                    await BillingWebhookService(self.session).emit(
                        lic.organization_id, "license.expiring",
                        {"license_key": lic.license_key, "expired_at": now.isoformat()},
                    )
        if expired:
            await self.session.flush()
        return expired
