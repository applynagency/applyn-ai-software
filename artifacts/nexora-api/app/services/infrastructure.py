"""Sprint 35B — InfrastructureService.

Orchestrates BYOI onboarding: decrypts a stored credential (via the 35A secret
manager), runs connection/permission/health checks, persists a customer-safe
status + readiness score, and exposes pre-deployment validation.

Does not touch deployment providers, agents, QA, or the DevOps chain.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.infrastructure.validator import InfrastructureValidator, ValidationReport
from app.models.credential import DeploymentCredential, InfrastructureStatus
from app.models.user import User
from app.repositories.credential import DeploymentCredentialRepository
from app.security.secrets import SecretManagerService

logger = get_logger(__name__)


class InfrastructureService:
    def __init__(self, session: AsyncSession, validator: InfrastructureValidator | None = None):
        self.session = session
        self.repo = DeploymentCredentialRepository(session)
        self.secret_manager = SecretManagerService(session)
        self.validator = validator or InfrastructureValidator()

    async def _get(self, credential_id: str, user: User, org_context: OrgContext) -> DeploymentCredential:
        organization_id = org_context.requires_organization
        credential = await self.repo.get_for_org(credential_id, organization_id)
        if not credential:
            raise NotFoundError("Credential", credential_id)
        return credential

    async def verify(
        self, credential_id: str, user: User, org_context: OrgContext
    ) -> tuple[DeploymentCredential, ValidationReport]:
        """Run full connection + permission + health checks and persist status."""
        # resolve_secret enforces read permission, active state, org scope, and
        # audits SECRET_USED; decrypted secret is used transiently only.
        credential, secret = await self.secret_manager.resolve_secret(
            credential_id,
            user=user,
            org_context=org_context,
            reason="infrastructure verification",
        )
        # Connection checks can block on network I/O — keep the event loop free.
        report = await asyncio.to_thread(self.validator.validate, credential.provider, secret)

        status = (
            InfrastructureStatus.VERIFIED.value
            if report.verified
            else InfrastructureStatus.VERIFICATION_FAILED.value
        )
        credential = await self.repo.update(
            credential,
            status=status,
            readiness_score=report.score,
            last_verified_at=datetime.now(UTC),
            verification_details={"checks": [c.as_dict() for c in report.checks]},
        )
        logger.info(
            "infrastructure_verified",
            credential_id=credential.id,
            provider=credential.provider,
            status=status,
            score=report.score,
        )
        return credential, report

    async def get_status(
        self, credential_id: str, user: User, org_context: OrgContext
    ) -> DeploymentCredential:
        return await self._get(credential_id, user, org_context)

    async def validate_for_deploy(
        self, credential_id: str, user: User, org_context: OrgContext
    ) -> dict:
        """Pre-deployment validation. Always returns customer-safe guidance.

        Re-runs the live checks so the customer gets a fresh verdict right before
        deploying. Never raises provider exceptions to the caller.
        """
        credential, report = await self.verify(credential_id, user, org_context)
        return {
            "credential_id": credential.id,
            "provider": credential.provider,
            "ready": report.verified,
            "readiness_score": report.score,
            "status": credential.status,
            "checks": [c.as_dict() for c in report.checks],
            "guidance": report.guidance,
        }
