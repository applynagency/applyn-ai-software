"""Sprint 35A — SecretManagerService.

Responsibilities:
- encrypt a credential secret before storage (AES-256-GCM)
- decrypt only when a deployment executes (``resolve_secret``)
- rotate secrets (``rotate``/``update_credential`` with a new secret)
- revoke secrets (``revoke``/``delete_credential``)
- audit every secret lifecycle/usage event (``secret_access_audit``)

No method ever returns the decrypted payload to an API response; only
``resolve_secret`` returns plaintext and is for in-process deployment use only.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.credential import (
    CredentialProvider,
    DeploymentCredential,
    SecretAuditEvent,
)
from app.models.user import User
from app.repositories.credential import (
    DeploymentCredentialRepository,
    SecretAccessAuditRepository,
)
from app.security.secrets.crypto import get_cipher
from app.tenancy.permissions import can_read_resources, can_write_resources

logger = get_logger(__name__)

# Required secret fields per provider. Anything extra is preserved but unused.
REQUIRED_FIELDS: dict[str, list[str]] = {
    CredentialProvider.AZURE.value: [
        "subscription_id",
        "tenant_id",
        "client_id",
        "client_secret",
    ],
    CredentialProvider.AWS.value: ["access_key", "secret_key", "region"],
    CredentialProvider.KUBERNETES.value: ["kubeconfig"],
    CredentialProvider.VM.value: ["host", "username", "private_key"],
    # Sprint 39C — read-only investigation providers.
    CredentialProvider.GITHUB.value: ["token"],
    CredentialProvider.POSTGRESQL.value: [
        "host",
        "username",
        "password",
        "database",
    ],
    CredentialProvider.PROMETHEUS.value: ["endpoint"],
    CredentialProvider.GRAFANA.value: ["endpoint", "token"],
    CredentialProvider.DATADOG.value: ["api_key", "app_key"],
    CredentialProvider.GCP.value: ["project_id", "service_account_json"],
    # Sprint 47B — Integration Marketplace providers. The provider column is a
    # free-form String so these reuse the same encrypted store with no migration.
    "GITLAB": ["token"],
    "BITBUCKET": ["username", "app_password"],
    "JIRA": ["base_url", "email", "api_token"],
    "NEW_RELIC": ["account_id", "api_key"],
    "PAGERDUTY": ["api_key"],
    "SLACK": ["bot_token"],
    # Sprint 58A.1 — Teams verification uses Microsoft Graph app credentials so
    # connectivity/identity/scopes can be genuinely confirmed (not a webhook).
    "MICROSOFT_TEAMS": ["tenant_id", "client_id", "client_secret"],
    "GCP": ["project_id", "service_account_json"],
    "CLOUDWATCH": ["access_key", "secret_key", "region"],
    "ARGOCD": ["endpoint", "token"],
    "TERRAFORM": ["organization", "token"],
    "JENKINS": ["endpoint", "username", "api_token"],
    "AZURE_DEVOPS": ["organization", "pat"],
    "CIRCLECI": ["api_token"],
    "HASHICORP_VAULT": ["endpoint", "token"],
    "LOKI": ["endpoint"],
    "ELASTIC": ["endpoint", "api_key"],
    "OPSGENIE": ["api_key"],
    "SONARQUBE": ["endpoint", "token"],
    # P3 enterprise + extended marketplace providers
    "ALERTMANAGER": ["endpoint"],
    "SPLUNK": ["endpoint", "token"],
    "SERVICENOW": ["instance_url", "username", "password"],
    "OPENTELEMETRY": ["endpoint"],
    "SENTRY": ["endpoint", "token"],
    "DYNATRACE": ["environment_id", "api_token"],
    "BUILDKITE": ["organization", "api_token"],
    "HARNESS": ["account_id", "api_key"],
    "FLUX": ["kubeconfig"],
}

# Field names that must NEVER be logged or surfaced anywhere.
SECRET_FIELD_NAMES = {
    "client_secret",
    "secret_key",
    "private_key",
    "kubeconfig",
    "password",
    "token",
    "api_key",
    "app_key",
    # Sprint 47B — marketplace secret fields.
    "app_password",
    "api_token",
    "bot_token",
    "webhook_url",
    "service_account_json",
    "pat",
}


class SecretManagerService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = DeploymentCredentialRepository(session)
        self.audit = SecretAccessAuditRepository(session)
        self._cipher = None

    @property
    def cipher(self):
        if self._cipher is None:
            self._cipher = get_cipher()
        return self._cipher

    # ----------------------------- guards ----------------------------- #
    def _ensure_write(self, user: User, org_context: OrgContext) -> None:
        if not user.is_superuser and (
            not org_context.role or not can_write_resources(org_context.role)
        ):
            raise ForbiddenError()

    def _ensure_read(self, user: User, org_context: OrgContext) -> None:
        if not user.is_superuser and (
            not org_context.role or not can_read_resources(org_context.role)
        ):
            raise ForbiddenError()

    def _validate_secret(self, provider: str, secret: dict) -> None:
        if provider not in REQUIRED_FIELDS:
            raise ValidationError(f"Unsupported provider: {provider}")
        missing = [f for f in REQUIRED_FIELDS[provider] if not secret.get(f)]
        if missing:
            raise ValidationError(
                f"{provider} credential missing required fields: {', '.join(missing)}"
            )

    def _encrypt(self, secret: dict) -> str:
        # Normalize to JSON then encrypt the whole blob as one ciphertext.
        return self.cipher.encrypt(json.dumps(secret, separators=(",", ":")))

    # ----------------------------- CRUD ------------------------------- #
    async def create_credential(
        self,
        *,
        provider: str,
        name: str,
        secret: dict,
        user: User,
        org_context: OrgContext,
    ) -> DeploymentCredential:
        self._ensure_write(user, org_context)
        organization_id = org_context.requires_organization
        self._validate_secret(provider, secret)

        credential = await self.repo.create(
            organization_id=organization_id,
            provider=provider,
            name=name,
            encrypted_payload=self._encrypt(secret),
            is_active=True,
            created_by=user.id,
        )
        await self.audit.record(
            organization_id=organization_id,
            event=SecretAuditEvent.SECRET_CREATED.value,
            credential_id=credential.id,
            actor_user_id=user.id,
            reason="credential created",
        )
        logger.info(
            "secret_created",
            credential_id=credential.id,
            provider=provider,
            organization_id=organization_id,
        )
        return credential

    async def list_credentials(
        self, user: User, org_context: OrgContext
    ) -> tuple[list[DeploymentCredential], int]:
        self._ensure_read(user, org_context)
        organization_id = org_context.requires_organization
        return await self.repo.list_for_org(organization_id)

    async def get_credential(
        self, credential_id: str, user: User, org_context: OrgContext
    ) -> DeploymentCredential:
        self._ensure_read(user, org_context)
        organization_id = org_context.requires_organization
        credential = await self.repo.get_for_org(credential_id, organization_id)
        if not credential:
            raise NotFoundError("Credential", credential_id)
        return credential

    async def update_credential(
        self,
        credential_id: str,
        *,
        name: str | None,
        secret: dict | None,
        is_active: bool | None,
        user: User,
        org_context: OrgContext,
    ) -> DeploymentCredential:
        self._ensure_write(user, org_context)
        organization_id = org_context.requires_organization
        credential = await self.repo.get_for_org(credential_id, organization_id)
        if not credential:
            raise NotFoundError("Credential", credential_id)

        changes: dict = {}
        rotated = False
        revoked = False
        if name is not None:
            changes["name"] = name
        if secret is not None:
            self._validate_secret(credential.provider, secret)
            changes["encrypted_payload"] = self._encrypt(secret)
            rotated = True
        if is_active is not None:
            changes["is_active"] = is_active
            revoked = is_active is False

        if changes:
            credential = await self.repo.update(credential, **changes)

        await self.audit.record(
            organization_id=organization_id,
            event=(
                SecretAuditEvent.SECRET_REVOKED.value
                if revoked
                else SecretAuditEvent.SECRET_UPDATED.value
            ),
            credential_id=credential.id,
            actor_user_id=user.id,
            reason="secret rotated" if rotated else ("revoked" if revoked else "metadata updated"),
        )
        logger.info(
            "secret_updated",
            credential_id=credential.id,
            rotated=rotated,
            revoked=revoked,
        )
        return credential

    async def delete_credential(
        self, credential_id: str, user: User, org_context: OrgContext
    ) -> None:
        self._ensure_write(user, org_context)
        organization_id = org_context.requires_organization
        credential = await self.repo.get_for_org(credential_id, organization_id)
        if not credential:
            raise NotFoundError("Credential", credential_id)
        await self.audit.record(
            organization_id=organization_id,
            event=SecretAuditEvent.SECRET_REVOKED.value,
            credential_id=credential.id,
            actor_user_id=user.id,
            reason="credential deleted",
        )
        await self.repo.hard_delete(credential)
        logger.info("secret_revoked", credential_id=credential_id)

    # ------------------------- runtime resolve ------------------------ #
    async def resolve_secret(
        self,
        credential_id: str,
        *,
        user: User,
        org_context: OrgContext,
        deployment_id: str | None = None,
        reason: str | None = None,
        audit: bool = True,
    ) -> tuple[DeploymentCredential, dict]:
        """Decrypt a credential for in-process deployment use.

        Returns ``(credential, plaintext_dict)``. Callers must use the plaintext
        transiently, never log it, and never persist it. When ``audit`` is True,
        records SECRET_USED and bumps ``last_used_at``; pass ``audit=False`` to
        defer auditing until the deployment_id is known, then call
        :meth:`record_usage`.
        """
        self._ensure_read(user, org_context)
        organization_id = org_context.requires_organization
        credential = await self.repo.get_for_org(credential_id, organization_id)
        if not credential:
            raise NotFoundError("Credential", credential_id)
        if not credential.is_active:
            raise ValidationError("Credential is revoked/inactive and cannot be used")

        payload = json.loads(self.cipher.decrypt(credential.encrypted_payload))

        if audit:
            await self.record_usage(
                credential,
                user=user,
                org_context=org_context,
                deployment_id=deployment_id,
                reason=reason,
            )
        return credential, payload

    async def record_usage(
        self,
        credential: DeploymentCredential,
        *,
        user: User,
        org_context: OrgContext,
        deployment_id: str | None = None,
        reason: str | None = None,
    ) -> None:
        """Mark a credential as used: bump last_used_at + write SECRET_USED."""
        organization_id = org_context.requires_organization
        await self.repo.update(credential, last_used_at=datetime.now(UTC))
        await self.audit.record(
            organization_id=organization_id,
            event=SecretAuditEvent.SECRET_USED.value,
            credential_id=credential.id,
            actor_user_id=user.id,
            reason=reason or "deployment execution",
            deployment_id=deployment_id,
        )
        logger.info(
            "secret_used",
            credential_id=credential.id,
            provider=credential.provider,
            deployment_id=deployment_id,
        )
