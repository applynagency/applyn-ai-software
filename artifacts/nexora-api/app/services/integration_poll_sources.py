"""Unified ingest credential resolution — marketplace connections + deployment creds."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.credential import DeploymentCredentialRepository
from app.repositories.integration import IntegrationConnectionRepository
from app.services.monitoring_ingestion import INGEST_POLLERS


@dataclass(frozen=True)
class IngestTarget:
    provider: str
    credential_id: str
    source: str  # "credential" | "integration"


async def list_ingest_targets(
    session: AsyncSession,
    organization_id: str,
    wanted_providers: set[str],
) -> list[IngestTarget]:
    """Deduplicated poll targets from deployment credentials and integration connections."""
    pollable = wanted_providers & set(INGEST_POLLERS.keys())
    if not pollable:
        return []

    seen: set[str] = set()
    targets: list[IngestTarget] = []

    cred_repo = DeploymentCredentialRepository(session)
    creds, _ = await cred_repo.list_for_org(organization_id, limit=300)
    for cred in creds:
        key = (cred.provider or "").upper()
        if not cred.is_active or key not in pollable or not cred.id:
            continue
        if cred.id in seen:
            continue
        seen.add(cred.id)
        targets.append(IngestTarget(provider=key, credential_id=cred.id, source="credential"))

    conn_repo = IntegrationConnectionRepository(session)
    for conn in await conn_repo.list_for_org(organization_id):
        key = (conn.integration_key or "").upper()
        if key not in pollable or not conn.credential_id:
            continue
        if conn.credential_id in seen:
            continue
        seen.add(conn.credential_id)
        targets.append(IngestTarget(
            provider=key, credential_id=conn.credential_id, source="integration",
        ))

    return targets


async def orgs_with_ingest_targets(session: AsyncSession, providers: set[str]) -> list[str]:
    """Organization IDs that have at least one ingestible connection or credential."""
    from sqlalchemy import select

    from app.models.credential import DeploymentCredential
    from app.models.integration import IntegrationConnection

    pollable = providers & set(INGEST_POLLERS.keys())
    if not pollable:
        return []

    orgs: set[str] = set()
    stmt = (
        select(DeploymentCredential.organization_id)
        .where(
            DeploymentCredential.is_active.is_(True),
            DeploymentCredential.provider.in_(sorted(pollable)),
        )
        .distinct()
    )
    orgs.update((await session.execute(stmt)).scalars().all())

    stmt2 = (
        select(IntegrationConnection.organization_id)
        .where(
            IntegrationConnection.integration_key.in_(sorted(pollable)),
            IntegrationConnection.credential_id.isnot(None),
        )
        .distinct()
    )
    orgs.update((await session.execute(stmt2)).scalars().all())
    return sorted(orgs)
