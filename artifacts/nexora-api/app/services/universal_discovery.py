"""Sprint 58A.2.1 — Universal Discovery Framework engine.

Turns EVERY connected integration into discovered assets — not just AWS / Azure
/ Kubernetes. A single provider-aware engine:

  1. enumerates an org's ``IntegrationConnection`` rows whose provider supports
     discovery (infrastructure adapters from 58A.2 + the new GitHub / GitLab /
     Jira / Slack / Teams adapters),
  2. transiently resolves each connection's encrypted credential (35A store),
  3. runs the real, read-only provider adapter across all of its domains,
  4. upserts the results into the Universal Resource Model (``DiscoveredAsset``)
     and diffs them against the previous inventory to emit RESOURCE_ADDED /
     RESOURCE_UPDATED / RESOURCE_REMOVED / OWNERSHIP_CHANGED / DEPLOYMENT_CHANGED
     events (REMOVED only for providers that scanned successfully so a transient
     failure is never mistaken for a deletion),
  5. rebuilds the Platform Knowledge Graph (nodes + cross-provider edges) and
     emits RELATIONSHIP_ADDED / RELATIONSHIP_REMOVED / SERVICE_CHANGED events.

The graph becomes the single source of truth the AI consumes (see
``ai_context``). SAFETY: read-only w.r.t. customer systems; one provider failing
never aborts the others; secrets are never stored, logged or surfaced.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError
from app.models.discovery_pipeline import ScanRunStatus, ScanTrigger
from app.models.organization import OrganizationMember, OrganizationRole
from app.models.universal_discovery import (
    DiscoveredAsset,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    UniversalEventType,
)
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.discovery_pipeline import DiscoveryScanRunRepository
from app.repositories.integration import IntegrationConnectionRepository
from app.repositories.universal_discovery import (
    DiscoveredAssetRepository,
    KnowledgeGraphRepository,
    UniversalDiscoveryEventRepository,
)
from app.schemas.discovery_pipeline import ScanProgressView
from app.schemas.universal_discovery import (
    AIContextResponse,
    DiscoveryEventView,
    DomainSummary,
    GraphEdgeView,
    GraphNodeView,
    KnowledgeGraphView,
    ProviderDomainStatus,
    UniversalAssetView,
    UniversalDiscoverySummary,
    UniversalSyncResponse,
)
from app.security.secrets import SecretManagerService
from app.services.graph import SERVICE_PREFIX, is_service_key, service_key
from app.services.universal_discovery_adapters import (
    PROVIDER_DOMAINS,
    UniversalAdapterError,
    UniversalResource,
    domains_for,
    node_key,
    run_universal_provider,
    supports_universal_discovery,
)
from app.tenancy.permissions import can_read_resources

logger = structlog.get_logger(__name__)

# Resource types treated as "services" for SERVICE_CHANGED events / AI services.
_SERVICE_LIKE = {
    "RDS", "ALB", "LAMBDA", "APP_SERVICE", "SQL_DATABASE", "STATEFULSET",
    "DEPLOYMENT", "SERVICE", "DATABASE", "LOAD_BALANCER", "CONTAINER_APP", "ECS", "EKS",
    "REPOSITORY", "PROJECT",
}
_MAX_CROSS_EDGES = 400


def _now() -> datetime:
    return datetime.now(UTC)


def _norm_name(value: str | None) -> str:
    if not value:
        return ""
    base = str(value).split("/")[-1].split(":")[-1]
    return base.strip().lower()


def _fingerprint(ur: UniversalResource) -> str:
    rels = sorted(
        (str(r.get("target_key") or ""), str(r.get("target_name") or ""), str(r.get("type") or ""))
        for r in (ur.relationships or [])
    )
    payload = {
        "health": ur.health, "status": ur.status, "owner": ur.owner,
        "region": ur.region, "account": ur.account, "environment": ur.environment,
        "display_name": ur.display_name, "tags": ur.tags or {},
        "source_updated_at": ur.updated_at, "relationships": rels,
    }
    return json.dumps(payload, sort_keys=True, default=str)


def _asset_fingerprint(a: DiscoveredAsset) -> str:
    rels = sorted(
        (str(r.get("target_key") or ""), str(r.get("target_name") or ""), str(r.get("type") or ""))
        for r in (a.relationships or [])
    )
    payload = {
        "health": a.health, "status": a.status, "owner": a.owner,
        "region": a.region, "account": a.account, "environment": a.environment,
        "display_name": a.display_name, "tags": a.tags or {},
        "source_updated_at": a.source_updated_at, "relationships": rels,
    }
    return json.dumps(payload, sort_keys=True, default=str)


def _key(provider: str, domain: str, resource_type: str, resource_id: str) -> tuple:
    return (provider, domain, resource_type, resource_id)


class UniversalDiscoveryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit_repo = AuditLogRepository(session)
        self.conn_repo = IntegrationConnectionRepository(session)
        self.scan_repo = DiscoveryScanRunRepository(session)
        self.asset_repo = DiscoveredAssetRepository(session)
        self.graph_repo = KnowledgeGraphRepository(session)
        self.event_repo = UniversalDiscoveryEventRepository(session)
        self.secret_manager = SecretManagerService(session)

    def _ensure_read(self, user, org_context) -> None:
        if not user.is_superuser and (not org_context.role or not can_read_resources(org_context.role)):
            raise ForbiddenError()

    # ------------------------------------------------------------------ run
    async def run_for_org(
        self, user, org_context, *, trigger: str = ScanTrigger.MANUAL.value,
        providers_filter: list[str] | None = None,
    ) -> UniversalSyncResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)

        filter_set = {p.upper() for p in providers_filter} if providers_filter else None
        connections = await self.conn_repo.list_for_org(organization_id)
        scannable = [
            c for c in connections
            if supports_universal_discovery(c.integration_key) and c.credential_id
            and (filter_set is None or c.integration_key in filter_set)
        ]

        scan = await self.scan_repo.create(
            organization_id=organization_id, trigger=trigger,
            status=ScanRunStatus.RUNNING.value,
            providers=sorted({c.integration_key for c in scannable}),
            connection_count=len(scannable), started_at=_now(), created_by=user.id,
        )
        await self.audit_repo.log(
            action="universal_discovery_started", resource_type="discovery_scan_run",
            resource_id=scan.id, user_id=user.id,
            details={"organization_id": organization_id, "tenant": organization_id,
                     "trigger": trigger, "connections": len(scannable)},
        )
        await self.session.flush()

        started = time.monotonic()
        discovered: list[UniversalResource] = []
        warnings: list[str] = []
        scanned_providers: set[str] = set()
        scanned = 0

        for conn in scannable:
            await self.scan_repo.update(
                scan, current_provider=conn.integration_key, current_account=conn.name,
                scanned_connections=scanned,
            )
            try:
                _, secret = await self.secret_manager.resolve_secret(
                    conn.credential_id, user=user, org_context=org_context,
                    reason="universal discovery", audit=False,
                )
            except Exception as exc:  # noqa: BLE001 - customer-safe; never leak internals
                logger.info("universal_discovery_credential_unavailable",
                            connection_id=conn.id, error=type(exc).__name__)
                warnings.append(f"{conn.integration_key}: credential unavailable; skipped.")
                continue
            try:
                resources = await run_universal_provider(conn.integration_key, secret)
            except UniversalAdapterError as exc:
                warnings.append(f"{conn.integration_key}: {exc}")
                continue
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - never surface provider internals
                logger.warning("universal_discovery_adapter_failed",
                               provider=conn.integration_key, error=type(exc).__name__)
                warnings.append(f"{conn.integration_key}: discovery failed unexpectedly.")
                continue

            scanned_providers.add(conn.integration_key)
            discovered.extend(resources)
            scanned += 1
            await self.scan_repo.update(
                scan, resources_found=len(discovered), scanned_connections=scanned,
            )

        # Persist assets + diff (REMOVED only for providers that scanned OK).
        added, updated, removed = await self._upsert_and_diff(
            organization_id, scan.id, discovered, scanned_providers,
        )
        # Rebuild the knowledge graph from the resulting inventory + emit edge events.
        await self._rebuild_graph(organization_id, scan.id, scanned_providers)

        if not scannable:
            warnings.append("No connected integrations support discovery yet.")
            status = ScanRunStatus.COMPLETED.value
        elif not scanned_providers:
            status = ScanRunStatus.FAILED.value
        elif warnings:
            status = ScanRunStatus.PARTIAL.value
        else:
            status = ScanRunStatus.COMPLETED.value

        scan = await self.scan_repo.update(
            scan, status=status, current_provider=None, current_account=None,
            resources_found=len(discovered), scanned_connections=scanned,
            added_count=added, removed_count=removed, modified_count=updated,
            finished_at=_now(), estimated_seconds=int(time.monotonic() - started),
            warnings=warnings,
        )
        await self.audit_repo.log(
            action="universal_discovery_finished", resource_type="discovery_scan_run",
            resource_id=scan.id, user_id=user.id,
            details={"organization_id": organization_id, "tenant": organization_id,
                     "status": status, "resources": len(discovered),
                     "providers": sorted(scanned_providers),
                     "added": added, "updated": updated, "removed": removed},
        )
        await self.session.commit()

        summary = await self._build_summary(organization_id, latest_scan=scan)
        events = await self.event_repo.list_for_scan(scan.id, organization_id)
        return UniversalSyncResponse(
            scan=ScanProgressView.model_validate(scan),
            summary=summary,
            events=[DiscoveryEventView.model_validate(e) for e in events],
        )

    # --------------------------------------------------------- upsert + diff
    async def _upsert_and_diff(
        self, organization_id: str, scan_id: str,
        discovered: list[UniversalResource], scanned_providers: set[str],
    ) -> tuple[int, int, int]:
        existing = await self.asset_repo.list_for_org(organization_id)
        existing_map = {
            _key(a.provider, a.domain, a.resource_type, a.resource_id): a for a in existing
        }
        seen_keys: set[tuple] = set()
        added = updated = removed = 0
        now = _now()

        for ur in discovered:
            k = _key(ur.provider, ur.domain, ur.resource_type, ur.resource_id)
            if k in seen_keys:
                continue  # de-dupe within a single scan
            seen_keys.add(k)
            fp = _fingerprint(ur)
            current = existing_map.get(k)
            if current is None:
                asset = await self.asset_repo.create(
                    organization_id=organization_id, scan_run_id=scan_id,
                    provider=ur.provider, domain=ur.domain, resource_type=ur.resource_type,
                    resource_id=ur.resource_id, resource_name=ur.resource_name,
                    display_name=ur.display_name, parent_id=ur.parent_id, owner=ur.owner,
                    region=ur.region, account=ur.account, environment=ur.environment,
                    health=ur.health, status=ur.status, tags=ur.tags or {},
                    relationships=ur.relationships or [], asset_metadata=ur.metadata or {},
                    source_created_at=ur.created_at, source_updated_at=ur.updated_at,
                    fingerprint=fp, first_seen_at=now, last_seen_at=now,
                )
                added += 1
                await self._event(organization_id, scan_id, UniversalEventType.RESOURCE_ADDED, ur)
                if ur.domain == "DEPLOYMENT":
                    await self._event(organization_id, scan_id, UniversalEventType.DEPLOYMENT_CHANGED, ur)
                elif ur.resource_type in _SERVICE_LIKE:
                    await self._event(organization_id, scan_id, UniversalEventType.SERVICE_CHANGED, ur)
                _ = asset
            else:
                changed = current.fingerprint != fp
                owner_changed = (current.owner or "") != (ur.owner or "")
                await self.asset_repo.update(
                    current, scan_run_id=scan_id, resource_name=ur.resource_name,
                    display_name=ur.display_name, parent_id=ur.parent_id, owner=ur.owner,
                    region=ur.region, account=ur.account, environment=ur.environment,
                    health=ur.health, status=ur.status, tags=ur.tags or {},
                    relationships=ur.relationships or [], asset_metadata=ur.metadata or {},
                    source_created_at=ur.created_at, source_updated_at=ur.updated_at,
                    fingerprint=fp, last_seen_at=now,
                )
                if changed:
                    updated += 1
                    await self._event(organization_id, scan_id, UniversalEventType.RESOURCE_UPDATED, ur)
                    if owner_changed:
                        await self._event(organization_id, scan_id,
                                          UniversalEventType.OWNERSHIP_CHANGED, ur)
                    if ur.domain == "DEPLOYMENT":
                        await self._event(organization_id, scan_id,
                                          UniversalEventType.DEPLOYMENT_CHANGED, ur)
                    elif ur.resource_type in _SERVICE_LIKE:
                        await self._event(organization_id, scan_id,
                                          UniversalEventType.SERVICE_CHANGED, ur)

        # REMOVED — only for providers that scanned successfully this run.
        for k, a in existing_map.items():
            if k in seen_keys or a.provider not in scanned_providers:
                continue
            await self._event_from_asset(organization_id, scan_id,
                                         UniversalEventType.RESOURCE_REMOVED, a)
            await self.session.delete(a)
            removed += 1
        await self.session.flush()
        return added, updated, removed

    async def _event(self, organization_id, scan_id, event_type, ur: UniversalResource) -> None:
        await self.event_repo.create(
            organization_id=organization_id, scan_run_id=scan_id, event_type=event_type.value,
            provider=ur.provider, domain=ur.domain, resource_type=ur.resource_type,
            resource_id=ur.resource_id, resource_name=ur.resource_name,
            details={"owner": ur.owner, "health": ur.health, "environment": ur.environment},
        )

    async def _event_from_asset(self, organization_id, scan_id, event_type, a: DiscoveredAsset) -> None:
        await self.event_repo.create(
            organization_id=organization_id, scan_run_id=scan_id, event_type=event_type.value,
            provider=a.provider, domain=a.domain, resource_type=a.resource_type,
            resource_id=a.resource_id, resource_name=a.resource_name,
            details={"owner": a.owner, "health": a.health},
        )

    # --------------------------------------------------------- knowledge graph
    async def _rebuild_graph(
        self, organization_id: str, scan_id: str, scanned_providers: set[str],
    ) -> None:
        assets = await self.asset_repo.list_for_org(organization_id)

        # Only asset-derived edges participate in the discovery diff. Curated
        # service-topology edges (``service:<id>`` keys) are preserved across
        # scans — they are a separate, user/onboarding-declared layer of the
        # single graph and are never wiped or re-derived by discovery.
        prev_edges = {
            (e.source_key, e.target_key, e.relationship_type)
            for e in await self.graph_repo.list_edges(organization_id)
            if not is_service_key(e.source_key)
        }

        # Wipe and rebuild only the asset-derived portion of the org's graph.
        await self.session.execute(
            delete(KnowledgeGraphEdge).where(
                KnowledgeGraphEdge.organization_id == organization_id,
                KnowledgeGraphEdge.source_key.notlike(f"{SERVICE_PREFIX}%"),
            ))
        await self.session.execute(
            delete(KnowledgeGraphNode).where(
                KnowledgeGraphNode.organization_id == organization_id,
                KnowledgeGraphNode.node_key.notlike(f"{SERVICE_PREFIX}%"),
            ))
        await self.session.flush()

        key_by_id: dict[str, str] = {}
        name_index: dict[str, list[tuple[str, str]]] = {}  # norm_name -> [(node_key, provider)]
        now = _now()

        for a in assets:
            nk = node_key(a.provider, a.domain, a.resource_type, a.resource_id)
            self.session.add(KnowledgeGraphNode(
                organization_id=organization_id, node_key=nk, node_type=a.resource_type,
                provider=a.provider, domain=a.domain, name=a.resource_name,
                display_name=a.display_name, asset_id=a.id,
                node_metadata={"owner": a.owner, "health": a.health, "environment": a.environment},
                last_seen_at=now,
            ))
            key_by_id[(a.provider, a.resource_id)] = nk
            if a.resource_type in _SERVICE_LIKE or a.domain in ("COLLABORATION", "BUSINESS"):
                name_index.setdefault(_norm_name(a.display_name or a.resource_name), []).append(
                    (nk, a.provider))
        await self.session.flush()

        node_keys = set(key_by_id.values())
        new_edges: set[tuple] = set()

        def _add_edge(src: str, tgt: str, rtype: str) -> None:
            if src == tgt or not src or not tgt:
                return
            sig = (src, tgt, rtype)
            if sig in new_edges:
                return
            new_edges.add(sig)

        # Explicit relationships declared by adapters.
        for a in assets:
            src = node_key(a.provider, a.domain, a.resource_type, a.resource_id)
            for rel in (a.relationships or []):
                rtype = rel.get("type") or "RELATES_TO"
                tgt = rel.get("target_key")
                if tgt and tgt in node_keys:
                    _add_edge(src, tgt, rtype)
                    continue
                tname = rel.get("target_name")
                if not tname:
                    continue
                # resolve by id (same provider) then by normalized name
                resolved = key_by_id.get((a.provider, tname))
                if not resolved:
                    candidates = name_index.get(_norm_name(tname)) or []
                    same = [ck for ck, p in candidates if p == a.provider]
                    resolved = (same or [ck for ck, _ in candidates] or [None])[0]
                if resolved:
                    _add_edge(src, resolved, rtype)

        # Cross-provider semantic links (Service ↔ Repo ↔ Slack channel ↔ Jira component…).
        cross = 0
        for _name, group in name_index.items():
            if not _name or len(group) < 2 or cross >= _MAX_CROSS_EDGES:
                continue
            uniq = group[:6]
            for i in range(len(uniq)):
                for j in range(i + 1, len(uniq)):
                    (k1, p1), (k2, p2) = uniq[i], uniq[j]
                    if p1 == p2:
                        continue
                    _add_edge(k1, k2, "RELATES_TO")
                    cross += 1
                    if cross >= _MAX_CROSS_EDGES:
                        break

        for src, tgt, rtype in new_edges:
            self.session.add(KnowledgeGraphEdge(
                organization_id=organization_id, source_key=src, target_key=tgt,
                relationship_type=rtype, last_seen_at=now,
            ))
        await self.session.flush()

        # Emit relationship change events (only where the source provider scanned).
        for sig in new_edges - prev_edges:
            src, tgt, rtype = sig
            if src.split(":")[0] in scanned_providers:
                await self.event_repo.create(
                    organization_id=organization_id, scan_run_id=scan_id,
                    event_type=UniversalEventType.RELATIONSHIP_ADDED.value,
                    provider=src.split(":")[0], details={"source": src, "target": tgt, "type": rtype},
                )
        for sig in prev_edges - new_edges:
            src, tgt, rtype = sig
            if src.split(":")[0] in scanned_providers:
                await self.event_repo.create(
                    organization_id=organization_id, scan_run_id=scan_id,
                    event_type=UniversalEventType.RELATIONSHIP_REMOVED.value,
                    provider=src.split(":")[0], details={"source": src, "target": tgt, "type": rtype},
                )
        await self.session.flush()
        await self._invalidate_graph_cache(organization_id)

    # ----------------------------------------------- service topology writer
    # Universal Discovery is the SOLE writer of the knowledge graph. Curated
    # service dependencies are written here (callers handle RBAC/validation/
    # audit/commit); no other service mutates nodes or edges.
    async def _ensure_service_node(
        self, organization_id: str, service_id: str, name: str | None = None
    ) -> KnowledgeGraphNode:
        key = service_key(service_id)
        stmt = select(KnowledgeGraphNode).where(
            KnowledgeGraphNode.organization_id == organization_id,
            KnowledgeGraphNode.node_key == key,
        )
        node = (await self.session.execute(stmt)).scalar_one_or_none()
        if node is None:
            node = KnowledgeGraphNode(
                organization_id=organization_id, node_key=key, node_type="SERVICE",
                name=name or service_id, last_seen_at=_now(),
            )
            self.session.add(node)
            await self.session.flush()
        elif name and node.name != name:
            node.name = name
            await self.session.flush()
        return node

    async def add_service_dependency(
        self, organization_id: str, *, source_service_id: str, target_service_id: str,
        dependency_type: str, source_name: str | None = None, target_name: str | None = None,
    ) -> KnowledgeGraphEdge:
        await self._ensure_service_node(organization_id, source_service_id, source_name)
        await self._ensure_service_node(organization_id, target_service_id, target_name)
        edge = await self.graph_repo.edges.create(
            organization_id=organization_id,
            source_key=service_key(source_service_id),
            target_key=service_key(target_service_id),
            relationship_type=dependency_type,
            edge_metadata={"dependency_type": dependency_type, "origin": "catalog"},
            last_seen_at=_now(),
        )
        await self._invalidate_graph_cache(organization_id)
        return edge

    async def remove_service_dependency(self, edge: KnowledgeGraphEdge) -> None:
        organization_id = edge.organization_id
        await self.session.delete(edge)
        await self.session.flush()
        await self._invalidate_graph_cache(organization_id)

    @staticmethod
    async def _invalidate_graph_cache(organization_id: str) -> None:
        from app.services.graph import invalidate_graph_cache

        await invalidate_graph_cache(organization_id)

    # --------------------------------------------------------------- queries
    async def _build_summary(
        self, organization_id: str, *, latest_scan=None
    ) -> UniversalDiscoverySummary:
        assets = await self.asset_repo.list_for_org(organization_id)
        connections = await self.conn_repo.list_for_org(organization_id)
        nodes = await self.graph_repo.list_nodes(organization_id)
        edges = await self.graph_repo.list_edges(organization_id)

        by_domain: dict[str, dict] = {}
        provider_counts: dict[str, int] = {}
        provider_asset_counts: dict[str, int] = {}
        for a in assets:
            provider_counts[a.provider] = provider_counts.get(a.provider, 0) + 1
            provider_asset_counts[a.provider] = provider_asset_counts.get(a.provider, 0) + 1
            d = by_domain.setdefault(a.domain, {"count": 0, "providers": set(), "types": {}})
            d["count"] += 1
            d["providers"].add(a.provider)
            d["types"][a.resource_type] = d["types"].get(a.resource_type, 0) + 1

        domains = [
            DomainSummary(domain=dom, asset_count=info["count"],
                          providers=sorted(info["providers"]), resource_type_counts=info["types"])
            for dom, info in sorted(by_domain.items())
        ]

        provider_status: list[ProviderDomainStatus] = []
        for c in connections:
            supported = supports_universal_discovery(c.integration_key)
            note = None
            if not supported:
                note = "Discovery not available for this provider yet."
            elif not c.credential_id:
                note = "No stored credential — reconnect to enable discovery."
            provider_status.append(ProviderDomainStatus(
                provider=c.integration_key, connection_name=c.name,
                domains=domains_for(c.integration_key),
                asset_count=provider_asset_counts.get(c.integration_key, 0),
                supported=supported, note=note,
            ))

        return UniversalDiscoverySummary(
            total_assets=len(assets), domains=domains, providers=provider_status,
            provider_counts=provider_counts, node_count=len(nodes), edge_count=len(edges),
            latest_scan=ScanProgressView.model_validate(latest_scan) if latest_scan else None,
        )

    async def summary(self, user, org_context) -> UniversalDiscoverySummary:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        latest = await self.scan_repo.latest_for_org(organization_id)
        return await self._build_summary(organization_id, latest_scan=latest)

    async def progress(self, user, org_context) -> ScanProgressView | None:
        """Latest scan-run progress for the org (live/most-recent discovery)."""
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        scan = await self.scan_repo.latest_for_org(organization_id)
        return ScanProgressView.model_validate(scan) if scan else None

    async def list_assets(
        self, user, org_context, *, domain: str | None = None,
        provider: str | None = None, limit: int = 500,
    ) -> list[UniversalAssetView]:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        rows = await self.asset_repo.query(
            organization_id, domain=domain.upper() if domain else None,
            provider=provider.upper() if provider else None, limit=limit,
        )
        return [UniversalAssetView.model_validate(r) for r in rows]

    async def graph(self, user, org_context) -> KnowledgeGraphView:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        nodes = await self.graph_repo.list_nodes(organization_id)
        edges = await self.graph_repo.list_edges(organization_id)
        return KnowledgeGraphView(
            nodes=[GraphNodeView.model_validate(n) for n in nodes],
            edges=[GraphEdgeView.model_validate(e) for e in edges],
            node_count=len(nodes), edge_count=len(edges),
        )

    async def timeline(self, user, org_context, *, limit: int = 100) -> list[DiscoveryEventView]:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        rows = await self.event_repo.list_for_org(organization_id, limit=limit)
        return [DiscoveryEventView.model_validate(r) for r in rows]

    # ------------------------------------------------------------ AI context
    async def ai_context(self, user, org_context, subject: str) -> AIContextResponse:
        """Return the discovered context the AI consumes for a service/incident.

        Matches discovered assets by name and walks the knowledge graph so an
        investigation/war-room/executive-report immediately knows the related
        repository, deployment, owner, Slack/Teams channel, Jira project and
        service dependencies — across every provider.
        """
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        norm = _norm_name(subject)
        assets = await self.asset_repo.list_for_org(organization_id)

        def _matches(a: DiscoveredAsset) -> bool:
            hay = " ".join(filter(None, [a.resource_name, a.display_name,
                                         (a.asset_metadata or {}).get("service_name")])).lower()
            return bool(norm) and (norm in hay or _norm_name(a.resource_name) == norm
                                   or _norm_name(a.display_name) == norm)

        matched = [a for a in assets if _matches(a)]
        matched_keys = {node_key(a.provider, a.domain, a.resource_type, a.resource_id) for a in matched}

        # Walk one hop in the graph to pull in directly related assets.
        edges = await self.graph_repo.list_edges(organization_id)
        neighbor_keys: set[str] = set()
        for e in edges:
            if e.source_key in matched_keys:
                neighbor_keys.add(e.target_key)
            if e.target_key in matched_keys:
                neighbor_keys.add(e.source_key)
        neighbor_keys -= matched_keys
        related = [
            a for a in assets
            if node_key(a.provider, a.domain, a.resource_type, a.resource_id) in neighbor_keys
        ]

        pool = matched + related

        def _view(items):
            return [UniversalAssetView.model_validate(a) for a in items]

        owners = sorted({a.owner for a in pool if a.owner})
        return AIContextResponse(
            subject=subject,
            matched_assets=_view(matched),
            repositories=_view([a for a in pool if a.resource_type in ("REPOSITORY", "PROJECT")]),
            deployments=_view([a for a in pool if a.domain == "DEPLOYMENT"]),
            services=_view([a for a in pool if a.resource_type in _SERVICE_LIKE
                            and a.domain == "INFRASTRUCTURE"]),
            owners=owners,
            slack_channels=_view([a for a in pool if a.provider == "SLACK"
                                  and a.resource_type in ("CHANNEL", "INCIDENT_CHANNEL")]),
            teams_channels=_view([a for a in pool if a.provider == "MICROSOFT_TEAMS"
                                  and a.resource_type == "CHANNEL"]),
            jira_projects=_view([a for a in pool if a.provider == "JIRA"
                                 and a.resource_type in ("PROJECT", "INCIDENT_PROJECT")]),
            related=_view(related),
        )


class UniversalDiscoveryRunner:
    """Stateless tick executed by the background loop (and by tests directly)."""

    async def run_once(self, session: AsyncSession) -> int:
        org_ids = await self._orgs_with_discoverable_connections(session)
        ran = 0
        for organization_id in org_ids:
            actor = await self._owner_actor(session, organization_id)
            if actor is None:
                continue
            user, org_context = actor
            try:
                await UniversalDiscoveryService(session).run_for_org(
                    user, org_context, trigger=ScanTrigger.SCHEDULED.value,
                )
                ran += 1
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("universal_discovery_scheduler_org_failed",
                             organization_id=organization_id, error=str(exc))
                await session.rollback()
        return ran

    async def _orgs_with_discoverable_connections(self, session: AsyncSession) -> list[str]:
        from app.models.integration import IntegrationConnection

        keys = sorted(set(PROVIDER_DOMAINS))
        stmt = (
            select(IntegrationConnection.organization_id)
            .where(IntegrationConnection.integration_key.in_(keys))
            .distinct()
        )
        return [row for row in (await session.execute(stmt)).scalars().all()]

    async def _owner_actor(
        self, session: AsyncSession, organization_id: str
    ) -> tuple[User, OrgContext] | None:
        stmt = (
            select(OrganizationMember)
            .where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.role == OrganizationRole.OWNER,
            )
            .order_by(OrganizationMember.created_at.asc())
            .limit(1)
        )
        member = (await session.execute(stmt)).scalar_one_or_none()
        if member is None:
            return None
        user = await session.get(User, member.user_id)
        if user is None:
            return None
        return user, OrgContext(user=user, organization_id=organization_id, role=OrganizationRole.OWNER)
