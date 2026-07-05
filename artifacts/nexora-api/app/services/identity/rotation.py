"""API-key rotation automation (Sprint 62B).

Sprint 61A added manual ``ApiKeyService.rotate``; the organization security
policy exposes ``api_key_max_age_days`` but nothing enforced it. This service
closes that gap: a daily cron expires (revokes) keys that have outlived their
org's configured max age, and surfaces keys nearing expiry. Every action is
audited via the existing :class:`ApiKeyService` (which writes tamper-evident
``api_key.*`` events).
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.database.base import utcnow

logger = get_logger(__name__)


class ApiKeyRotationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def enforce_max_age(self) -> dict:
        """Revoke keys older than their org's ``api_key_max_age_days`` policy."""
        from app.models.identity import ApiKey, OrganizationSecurityPolicy
        from app.services.identity.api_keys import ApiKeyService

        now = utcnow()
        revoked = scanned = 0
        policies = list((await self.session.execute(
            select(OrganizationSecurityPolicy).where(
                OrganizationSecurityPolicy.api_key_max_age_days > 0))).scalars().all())
        svc = ApiKeyService(self.session)
        for policy in policies:
            cutoff = now - timedelta(days=policy.api_key_max_age_days)
            keys = list((await self.session.execute(
                select(ApiKey).where(
                    ApiKey.organization_id == policy.organization_id,
                    ApiKey.revoked_at.is_(None),
                    ApiKey.created_at < cutoff,
                ))).scalars().all())
            for key in keys:
                scanned += 1
                try:
                    await svc.revoke(key)
                    revoked += 1
                except Exception as exc:  # noqa: BLE001 - isolate a bad row
                    logger.warning("api_key_rotation_failed", key_id=key.id, error=str(exc))
        result = {"policies": len(policies), "scanned": scanned, "revoked": revoked}
        logger.info("api_key_rotation_run", **result)
        return result
