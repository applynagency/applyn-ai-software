"""Sprint 47B - Integration Marketplace service.

Lists supported integrations, connects them (reusing the 35A encrypted
credential framework), runs read-only verification of credential configuration
and granted read scopes, and reports connection status / health / last sync /
permissions.

SAFETY: verification is strictly read-only - it inspects stored credential
configuration and never calls a remote system to mutate or act on it. Secrets
are stored only as the 35A AES-256-GCM envelope and never surfaced.
"""

from __future__ import annotations

import time
from collections import Counter
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NexoraException, ValidationError
from app.models.integration import ConnectionHealth, ConnectionStatus
from app.repositories.audit import AuditLogRepository
from app.repositories.integration import (
    IntegrationCatalogRepository,
    IntegrationConnectionRepository,
)
from app.schemas.integration import (
    CatalogItem,
    CheckView,
    ConnectionView,
    MarketplaceResponse,
    MarketplaceSummary,
    UpdateConnectionCredentialsRequest,
    VerifyResponse,
)
from app.security.secrets import SecretManagerService
from app.services.integration_capabilities import enrichment_for, supports_pipeline_sync
from app.services.integration_definitions import INTEGRATION_DEFINITIONS
from app.services.integration_sync import IntegrationSyncService
from app.services.integration_verification import (
    VerificationResult,
    VStatus,
    verify_provider,
)
from app.tenancy.permissions import can_read_resources, can_write_resources

logger = structlog.get_logger(__name__)

# Map the real verification vocabulary onto the persisted connection model.
# CONNECTED is the ONLY status that yields VERIFIED/HEALTHY — nothing is ever
# marked healthy without the provider confirming the credential.
_STATUS_MAP = {
    VStatus.CONNECTED: (ConnectionStatus.VERIFIED.value, ConnectionHealth.HEALTHY.value, True),
    VStatus.PARTIAL: (ConnectionStatus.NEEDS_ATTENTION.value, ConnectionHealth.DEGRADED.value, False),
    VStatus.FAILED: (ConnectionStatus.NEEDS_ATTENTION.value, ConnectionHealth.UNHEALTHY.value, False),
    VStatus.UNAUTHORIZED: (ConnectionStatus.NEEDS_ATTENTION.value, ConnectionHealth.UNHEALTHY.value, False),
    VStatus.TIMEOUT: (ConnectionStatus.NEEDS_ATTENTION.value, ConnectionHealth.UNKNOWN.value, False),
}


def _now() -> datetime:
    return datetime.now(UTC)


def _credential_failure_result(message: str) -> VerificationResult:
    """A FAILED result used when the credential cannot be resolved (no provider call)."""
    return VerificationResult(
        connection_status=VStatus.FAILED, latency_ms=0, provider_version=None,
        verified_at=_now(), provider_identity={}, permissions=[], warnings=[],
        errors=[message], confidence=0,
    )


def _build_checks(result: VerificationResult) -> list[dict]:
    """Translate the real verification result into the legacy three-check shape
    the UI/clients already render. Names are stable for backward compatibility."""
    reached = result.connection_status in (VStatus.CONNECTED, VStatus.PARTIAL, VStatus.UNAUTHORIZED)
    authed = result.connection_status in (VStatus.CONNECTED, VStatus.PARTIAL)
    has_perms = bool(result.permissions)
    auth_msg = (
        "Provider confirmed the credentials." if authed
        else (result.errors[0] if result.errors else "The provider did not confirm the credentials.")
    )
    conn_msg = (
        "Reached the provider over a verified TLS connection." if reached
        else (result.errors[0] if result.errors else "Could not reach the provider.")
    )
    perm_msg = (
        f"Granted: {', '.join(result.permissions[:8])}." if has_perms
        else ("Authenticated; specific read scopes were not reported." if authed
              else "Permissions could not be confirmed.")
    )
    return [
        {"name": "Credentials configured", "passed": authed, "message": auth_msg},
        {"name": "Connectivity (read-only)", "passed": reached and authed, "message": conn_msg},
        {"name": "Read permissions", "passed": authed and (has_perms or result.connection_status == VStatus.CONNECTED),
         "message": perm_msg},
    ]


def _build_guidance(result: VerificationResult) -> str:
    if result.connection_status == VStatus.CONNECTED:
        if result.warnings:
            return "Connected. Note: " + " ".join(result.warnings)
        return "All checks passed. This integration is connected and verified against the live provider."
    if result.connection_status == VStatus.PARTIAL:
        return "Partially verified — authentication succeeded but some reads failed. " + " ".join(result.warnings)
    if result.connection_status == VStatus.UNAUTHORIZED:
        return "Authentication failed. Check the credentials and required permissions, then reconnect."
    if result.connection_status == VStatus.TIMEOUT:
        return "The provider did not respond in time. Check network reachability and try again."
    return "Action needed — " + (" ".join(result.errors) or "verification could not be completed.")


class IntegrationMarketplaceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit_repo = AuditLogRepository(session)
        self.catalog_repo = IntegrationCatalogRepository(session)
        self.conn_repo = IntegrationConnectionRepository(session)
        self.secret_manager = SecretManagerService(session)

    # --------------------------------------------------------------- guards
    def _ensure_read(self, user, org_context) -> None:
        if not user.is_superuser and (not org_context.role or not can_read_resources(org_context.role)):
            raise ForbiddenError()

    def _ensure_write(self, user, org_context) -> None:
        if not user.is_superuser and (not org_context.role or not can_write_resources(org_context.role)):
            raise ForbiddenError()

    # --------------------------------------------------------------- catalog
    async def _seed_catalog(self) -> None:
        """Idempotently ensure global catalogue rows exist for every definition."""
        existing = {c.integration_key for c in await self.catalog_repo.list_global()}
        created = False
        for key, d in INTEGRATION_DEFINITIONS.items():
            if key in existing:
                continue
            await self.catalog_repo.create(
                organization_id=None, integration_key=key, name=d["name"],
                category=d["category"], description=d.get("description"),
                auth_type=d["auth_type"], required_fields=d["required_fields"],
                capabilities=d["capabilities"], docs_url=d.get("docs_url"), is_active=True,
            )
            created = True
        if created:
            await self.session.flush()

    async def list_marketplace(self, user, org_context) -> MarketplaceResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        await self._seed_catalog()

        catalog = await self.catalog_repo.list_global()
        connections = await self.conn_repo.list_for_org(organization_id)
        by_key: dict[str, list] = {}
        for c in connections:
            by_key.setdefault(c.integration_key, []).append(c)

        items: list[CatalogItem] = []
        for c in catalog:
            conns = by_key.get(c.integration_key, [])
            # surface the "best" status (VERIFIED > CONNECTED > NEEDS_ATTENTION > DISCONNECTED)
            status = self._best_status(conns)
            enrich = enrichment_for(c.integration_key)
            items.append(CatalogItem(
                integration_key=c.integration_key, name=c.name, category=c.category,
                description=c.description, auth_type=c.auth_type,
                required_fields=c.required_fields or [], capabilities=c.capabilities or [],
                docs_url=c.docs_url, is_active=c.is_active,
                connected=bool(conns), connection_count=len(conns), status=status,
                enrichment=enrich,
            ))

        counts = Counter(c.status for c in connections)
        live_capable = sum(1 for item in items if item.enrichment and item.enrichment.live_data)
        live_synced = sum(1 for c in connections if c.last_sync_at)
        summary = MarketplaceSummary(
            supported=len(catalog), connected=len(connections),
            verified=counts.get(ConnectionStatus.VERIFIED.value, 0),
            needs_attention=counts.get(ConnectionStatus.NEEDS_ATTENTION.value, 0),
            disconnected=counts.get(ConnectionStatus.DISCONNECTED.value, 0),
            live_capable=live_capable,
            live_synced=live_synced,
        )
        await self.audit_repo.log(
            action="integration_marketplace_viewed", resource_type="integration_catalog",
            resource_id=None, user_id=user.id,
            details={"organization_id": organization_id, "supported": len(catalog),
                     "connected": len(connections)},
        )
        await self.session.commit()
        return MarketplaceResponse(summary=summary, integrations=items)

    @staticmethod
    def _best_status(conns: list) -> str | None:
        if not conns:
            return None
        order = [ConnectionStatus.VERIFIED.value, ConnectionStatus.CONNECTED.value,
                 ConnectionStatus.NEEDS_ATTENTION.value, ConnectionStatus.DISCONNECTED.value]
        statuses = {c.status for c in conns}
        for s in order:
            if s in statuses:
                return s
        return next(iter(statuses))

    # --------------------------------------------------------------- connect
    async def connect(self, user, org_context, req) -> ConnectionView:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)

        key = (req.integration_key or "").upper()
        definition = INTEGRATION_DEFINITIONS.get(key)
        if definition is None:
            raise ValidationError(f"Unsupported integration: {req.integration_key}")

        name = req.name or definition["name"]
        # Reuse 35A credential framework: validates required fields + encrypts (AES-256-GCM).
        credential = await self.secret_manager.create_credential(
            provider=key, name=f"{name} ({key})", secret=req.credentials,
            user=user, org_context=org_context,
        )
        connection = await self.conn_repo.create(
            organization_id=organization_id, integration_key=key, name=name,
            credential_id=credential.id, status=ConnectionStatus.CONNECTED.value,
            health=ConnectionHealth.UNKNOWN.value, readiness_score=0,
            permissions_granted=[], created_by=user.id,
        )
        await self.audit_repo.log(
            action="integration_connected", resource_type="integration_connection",
            resource_id=connection.id, user_id=user.id,
            details={"organization_id": organization_id, "integration": key},
        )
        await self.session.commit()
        return self._connection_view(connection)

    # --------------------------------------------------------------- verify
    async def verify(self, user, org_context, req) -> VerifyResponse:
        """Sprint 58A.1 — REAL, read-only verification against the live provider.

        Decrypts the stored credential transiently and probes the actual remote
        platform. The connection is only marked VERIFIED/HEALTHY when the
        provider itself confirms the credential. No simulation, no fabricated
        HEALTHY status, secrets never surfaced.
        """
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)

        connection = await self.conn_repo.get_for_org(req.connection_id, organization_id)
        if connection is None:
            raise NexoraException("Connection not found.", status_code=404)

        provider = connection.integration_key
        await self.audit_repo.log(
            action="integration_verification_started", resource_type="integration_connection",
            resource_id=connection.id, user_id=user.id,
            details={"organization_id": organization_id, "tenant": organization_id, "provider": provider},
        )

        # Resolve (decrypt) the credential transiently. If it is missing/revoked
        # we never reach the provider — report FAILED, never VERIFIED.
        secret: dict | None = None
        cred_error: str | None = None
        try:
            if not connection.credential_id:
                raise ValidationError("No credential attached.")
            _, secret = await self.secret_manager.resolve_secret(
                connection.credential_id, user=user, org_context=org_context,
                reason="integration verification", audit=False,
            )
        except Exception as exc:  # noqa: BLE001 - customer-safe, never leak internals
            logger.info("integration_verify_credential_unavailable",
                        connection_id=connection.id, error=type(exc).__name__)
            cred_error = "Credential is missing or revoked. Reconnect to continue."

        started = time.monotonic()
        if secret is None:
            result = _credential_failure_result(cred_error or "Credential unavailable.")
        else:
            result = await verify_provider(provider, secret)
        # Best-effort guard: in case anything slips through, latency is real.
        if result.latency_ms == 0 and secret is not None:
            result.latency_ms = int((time.monotonic() - started) * 1000)

        status, health, verified = _STATUS_MAP.get(
            result.connection_status,
            (ConnectionStatus.NEEDS_ATTENTION.value, ConnectionHealth.UNHEALTHY.value, False),
        )
        checks = _build_checks(result)
        guidance = _build_guidance(result)

        now = _now()
        details = {
            "checks": checks,
            **result.to_dict(),
        }
        connection = await self.conn_repo.update(
            connection, status=status, health=health, readiness_score=result.confidence,
            permissions_granted=result.permissions, verification_details=details,
            last_verified_at=now,
            last_sync_at=connection.last_sync_at,
        )
        if verified:
            connection = await self._sync_after_verify(user, org_context, connection)

        finished_action = (
            "integration_verification_finished" if result.connection_status == VStatus.CONNECTED
            else "integration_verification_failed"
        )
        for action in (finished_action, "integration_verified"):
            await self.audit_repo.log(
                action=action, resource_type="integration_connection",
                resource_id=connection.id, user_id=user.id,
                details={
                    "organization_id": organization_id, "tenant": organization_id,
                    "provider": provider, "verified": verified,
                    "connection_status": result.connection_status,
                    "duration_ms": result.latency_ms, "confidence": result.confidence,
                },
            )
        await self.session.commit()

        return VerifyResponse(
            connection_id=connection.id, integration_key=provider,
            verified=verified, status=status, health=health, readiness_score=result.confidence,
            checks=[CheckView(**c) for c in checks], permissions_granted=result.permissions,
            guidance=guidance,
            connection_status=result.connection_status, latency_ms=result.latency_ms,
            provider_version=result.provider_version, verified_at=result.verified_at,
            provider_identity=result.provider_identity, permissions=result.permissions,
            warnings=result.warnings, errors=result.errors, confidence=result.confidence,
        )

    # --------------------------------------------------------------- list/del
    async def list_connections(self, user, org_context) -> list[ConnectionView]:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        rows = await self.conn_repo.list_for_org(organization_id)
        return [self._connection_view(c) for c in rows]

    async def disconnect(self, user, org_context, connection_id: str) -> None:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        connection = await self.conn_repo.get_for_org(connection_id, organization_id)
        if connection is None:
            raise NexoraException("Connection not found.", status_code=404)
        # Revoke + remove the encrypted credential via the 35A framework (audited).
        if connection.credential_id:
            try:
                await self.secret_manager.delete_credential(
                    connection.credential_id, user=user, org_context=org_context)
            except Exception as exc:  # noqa: BLE001
                logger.info("integration_credential_already_gone",
                            connection_id=connection.id, error=str(exc))
        await self.audit_repo.log(
            action="integration_disconnected", resource_type="integration_connection",
            resource_id=connection.id, user_id=user.id,
            details={"organization_id": organization_id, "integration": connection.integration_key},
        )
        await self.conn_repo.hard_delete(connection)
        await self.session.commit()

    async def update_connection_credentials(
        self, user, org_context, connection_id: str, req,
    ) -> ConnectionView:
        """Rotate or rename the encrypted credential backing a connection."""
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        connection = await self.conn_repo.get_for_org(connection_id, organization_id)
        if connection is None:
            raise NexoraException("Connection not found.", status_code=404)
        if not connection.credential_id:
            raise ValidationError("No credential attached to this connection.")
        if req.credentials:
            definition = INTEGRATION_DEFINITIONS.get(connection.integration_key)
            if definition is None:
                raise ValidationError(f"Unsupported integration: {connection.integration_key}")
        await self.secret_manager.update_credential(
            connection.credential_id,
            name=req.name,
            secret=req.credentials,
            is_active=None,
            user=user,
            org_context=org_context,
        )
        if req.name:
            connection = await self.conn_repo.update(connection, name=req.name)
        connection = await self.conn_repo.update(
            connection,
            status=ConnectionStatus.CONNECTED.value,
            health=ConnectionHealth.UNKNOWN.value,
            readiness_score=0,
        )
        await self.audit_repo.log(
            action="integration_credentials_rotated",
            resource_type="integration_connection",
            resource_id=connection.id,
            user_id=user.id,
            details={"organization_id": organization_id, "integration": connection.integration_key},
        )
        await self.session.commit()
        return self._connection_view(connection)

    async def _sync_after_verify(self, user, org_context, connection):
        """Pull live data after a successful verify (pipelines or mark sync time)."""
        key = (connection.integration_key or "").upper()
        if supports_pipeline_sync(key) and connection.credential_id:
            try:
                await IntegrationSyncService(self.session).sync_connection(
                    user, org_context, connection.id, sync_runs=True,
                )
                connection = await self.conn_repo.get_for_org(connection.id, connection.organization_id)
            except Exception as exc:  # noqa: BLE001
                logger.info("integration_auto_sync_failed", connection_id=connection.id, error=type(exc).__name__)
                connection = await self.conn_repo.update(connection, last_sync_at=_now())
        else:
            connection = await self.conn_repo.update(connection, last_sync_at=_now())
        return connection

    # --------------------------------------------------------------- shaping
    @staticmethod
    def _connection_view(c) -> ConnectionView:
        details = c.verification_details or {}
        checks = [CheckView(**ch) for ch in (details.get("checks") or [])]
        return ConnectionView(
            id=c.id, organization_id=c.organization_id, integration_key=c.integration_key,
            name=c.name, status=c.status, health=c.health, readiness_score=c.readiness_score,
            permissions_granted=c.permissions_granted or [], checks=checks,
            last_verified_at=c.last_verified_at, last_sync_at=c.last_sync_at, created_at=c.created_at,
            enrichment=enrichment_for(c.integration_key),
            connection_status=details.get("connection_status"),
            provider_version=details.get("provider_version"),
            latency_ms=details.get("latency_ms"),
            provider_identity=details.get("provider_identity") or {},
            warnings=details.get("warnings") or [],
            errors=details.get("errors") or [],
            confidence=details.get("confidence"),
        )
