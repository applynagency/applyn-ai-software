"""The single graph platform for Nexora.

There is exactly ONE graph store — the Platform Knowledge Graph
(``KnowledgeGraphNode`` / ``KnowledgeGraphEdge``) owned by Universal Discovery —
and exactly ONE traversal engine, :class:`GraphService` (+ :class:`GraphAdjacency`).

Every dependency lookup, blast-radius query, topology view and AI grounding goes
through here; there are no other traversal algorithms or graph stores anywhere
else in the codebase.

Service-topology edges live in the knowledge graph keyed by ``service:<id>`` node
keys (``relationship_type`` = the dependency type). This module reads them and
exposes a service-id-keyed adjacency so callers work in terms of the service
catalog while the graph remains the single source of truth.

Direction & terminology (unchanged from the original 44B engine):
* Edge: source depends on target.
* dependencies / downstream: services this one depends on  (follow source→target).
* dependents   / upstream:   services that depend on this one (follow target←source).
* Blast radius of a failure on X = X's transitive dependents.

All traversal is cycle-safe (visited set) and runs in O(V+E) over an in-memory
adjacency built once per request (and memoised per organization on the service
instance).
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.universal_discovery import KnowledgeGraphEdge
from app.repositories.universal_discovery import KnowledgeGraphRepository

SERVICE_PREFIX = "service:"


def graph_cache_namespace(organization_id: str) -> str:
    """Versioned distributed-cache namespace for an org's graph data."""
    return f"graph:{organization_id}"


async def invalidate_graph_cache(organization_id: str) -> None:
    """Invalidate every cached graph projection for an org (called by the writer)."""
    from app.redis import cache

    try:
        await cache.invalidate(graph_cache_namespace(organization_id))
    except Exception:  # pragma: no cover - cache must not break writes
        pass


def service_key(service_id: str) -> str:
    """Knowledge-graph node key for a catalogued service."""
    return f"{SERVICE_PREFIX}{service_id}"


def is_service_key(key: str | None) -> bool:
    return bool(key) and key.startswith(SERVICE_PREFIX)


def service_id_from_key(key: str) -> str:
    return key[len(SERVICE_PREFIX):]


@dataclass
class ServiceEdge:
    """A service→service dependency edge projected from the knowledge graph."""

    id: str
    organization_id: str
    source_service_id: str
    target_service_id: str
    dependency_type: str
    created_at: datetime | None = None


def _edge_to_dict(e: ServiceEdge) -> dict:
    return {
        "id": e.id,
        "organization_id": e.organization_id,
        "source_service_id": e.source_service_id,
        "target_service_id": e.target_service_id,
        "dependency_type": e.dependency_type,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


def _edge_from_dict(d: dict) -> ServiceEdge:
    created = d.get("created_at")
    return ServiceEdge(
        id=d["id"],
        organization_id=d["organization_id"],
        source_service_id=d["source_service_id"],
        target_service_id=d["target_service_id"],
        dependency_type=d["dependency_type"],
        created_at=datetime.fromisoformat(created) if created else None,
    )


class GraphAdjacency:
    """In-memory directed adjacency with the single set of traversal algorithms.

    Built once from a list of (source, target) id pairs. Node identifiers are
    opaque strings (service ids for the service topology). Centralizes BFS, DFS,
    upstream/downstream, shortest path, impact radius and critical path so no
    traversal logic is duplicated elsewhere.
    """

    def __init__(self, edges: list[tuple[str, str]]):
        # out_edges[source] = targets it depends on (downstream)
        # in_edges[target]  = sources that depend on it (upstream)
        self.out_edges: dict[str, set[str]] = defaultdict(set)
        self.in_edges: dict[str, set[str]] = defaultdict(set)
        for source, target in edges:
            self.out_edges[source].add(target)
            self.in_edges[target].add(source)

    # -- core BFS/DFS ------------------------------------------------------
    def bfs(self, start: str, adj: dict[str, set[str]]) -> tuple[set[str], set[str]]:
        """Return (direct, all_transitive_excluding_start). Cycle-safe, O(V+E)."""
        direct = set(adj.get(start, set()))
        seen: set[str] = set()
        q = deque(direct)
        while q:
            node = q.popleft()
            if node in seen or node == start:
                continue
            seen.add(node)
            for nxt in adj.get(node, set()):
                if nxt not in seen and nxt != start:
                    q.append(nxt)
        return direct, seen

    def dfs(self, start: str, adj: dict[str, set[str]]) -> list[str]:
        """Depth-first order of nodes reachable from ``start`` (excludes start)."""
        order: list[str] = []
        seen: set[str] = set()

        def _visit(node: str) -> None:
            for nxt in sorted(adj.get(node, set())):
                if nxt != start and nxt not in seen:
                    seen.add(nxt)
                    order.append(nxt)
                    _visit(nxt)

        _visit(start)
        return order

    # -- directional helpers ----------------------------------------------
    def dependencies(self, start: str) -> tuple[set[str], set[str]]:
        """(direct, transitive) services ``start`` depends on (downstream)."""
        return self.bfs(start, self.out_edges)

    def dependents(self, start: str) -> tuple[set[str], set[str]]:
        """(direct, transitive) services that depend on ``start`` (upstream)."""
        return self.bfs(start, self.in_edges)

    def downstream(self, start: str) -> set[str]:
        return self.bfs(start, self.out_edges)[1]

    def upstream(self, start: str) -> set[str]:
        return self.bfs(start, self.in_edges)[1]

    def dependency_traversal(self, start: str) -> set[str]:
        """All transitive dependencies of ``start`` (alias of downstream)."""
        return self.downstream(start)

    def impact_radius(self, start: str) -> set[str]:
        """Blast radius: transitive dependents impacted by a failure on ``start``."""
        return self.upstream(start)

    # -- paths -------------------------------------------------------------
    def shortest_path(self, source: str, target: str) -> list[str] | None:
        """Shortest directed dependency path source→target (incl. endpoints)."""
        if source == target:
            return [source]
        prev: dict[str, str] = {}
        seen = {source}
        q = deque([source])
        while q:
            node = q.popleft()
            for nxt in self.out_edges.get(node, set()):
                if nxt in seen:
                    continue
                seen.add(nxt)
                prev[nxt] = node
                if nxt == target:
                    path = [target]
                    while path[-1] != source:
                        path.append(prev[path[-1]])
                    return list(reversed(path))
                q.append(nxt)
        return None

    def critical_path(self) -> list[str]:
        """Longest dependency chain (most fragile path). Cycle-safe via memo."""
        nodes = set(self.out_edges) | set(self.in_edges)
        memo: dict[str, list[str]] = {}
        on_stack: set[str] = set()

        def longest(node: str) -> list[str]:
            if node in memo:
                return memo[node]
            if node in on_stack:  # cycle guard
                return [node]
            on_stack.add(node)
            best: list[str] = []
            for nxt in self.out_edges.get(node, set()):
                cand = longest(nxt)
                if len(cand) > len(best):
                    best = cand
            on_stack.discard(node)
            memo[node] = [node, *best]
            return memo[node]

        overall: list[str] = []
        for n in nodes:
            cand = longest(n)
            if len(cand) > len(overall):
                overall = cand
        return overall

    def has_cycle(self) -> bool:
        color: dict[str, int] = {}
        nodes = set(self.out_edges) | set(self.in_edges)

        def visit(n: str) -> bool:
            color[n] = 1
            for m in self.out_edges.get(n, set()):
                c = color.get(m, 0)
                if c == 1:
                    return True
                if c == 0 and visit(m):
                    return True
            color[n] = 2
            return False

        for node in nodes:
            if color.get(node, 0) == 0 and visit(node):
                return True
        return False


class GraphService:
    """Read access + traversal over the single Platform Knowledge Graph.

    Reads only. The sole graph writer is
    :class:`app.services.universal_discovery.UniversalDiscoveryService`.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.graph_repo = KnowledgeGraphRepository(session)
        self._edge_cache: dict[str, list[ServiceEdge]] = {}

    async def _service_edges(self, organization_id: str) -> list[ServiceEdge]:
        # Request-scoped memoization first (one DB hit per service instance).
        if organization_id in self._edge_cache:
            return self._edge_cache[organization_id]
        # Cross-request distributed cache (versioned, auto-invalidated on writes).
        edges = await self._cached_service_edges(organization_id)
        self._edge_cache[organization_id] = edges
        return edges

    async def _cached_service_edges(self, organization_id: str) -> list[ServiceEdge]:
        import time

        from app.observability import metrics
        from app.redis import cache

        ns = graph_cache_namespace(organization_id)
        started = time.perf_counter()
        cached = await cache.versioned_get(ns, "service_edges")
        if cached is not None:
            try:
                edges = [_edge_from_dict(d) for d in cached]
                metrics.observe_graph_traversal(
                    "load_service_edges", time.perf_counter() - started, cache="hit"
                )
                return edges
            except Exception:  # pragma: no cover - defensive on schema drift
                pass
        edges = await self._load_service_edges(organization_id)
        metrics.observe_graph_traversal(
            "load_service_edges", time.perf_counter() - started, cache="miss"
        )
        try:
            await cache.versioned_set(
                ns,
                "service_edges",
                value=[_edge_to_dict(e) for e in edges],
                ttl=settings.GRAPH_CACHE_TTL_SECONDS,
            )
        except Exception:  # pragma: no cover - cache must not break reads
            pass
        return edges

    async def _load_service_edges(self, organization_id: str) -> list[ServiceEdge]:
        rows = await self.graph_repo.list_edges(organization_id)
        return [
            ServiceEdge(
                id=e.id,
                organization_id=e.organization_id,
                source_service_id=service_id_from_key(e.source_key),
                target_service_id=service_id_from_key(e.target_key),
                dependency_type=e.relationship_type,
                created_at=e.created_at,
            )
            for e in rows
            if is_service_key(e.source_key) and is_service_key(e.target_key)
        ]

    def _invalidate(self, organization_id: str) -> None:
        self._edge_cache.pop(organization_id, None)

    async def list_service_edges(self, organization_id: str) -> list[ServiceEdge]:
        return list(await self._service_edges(organization_id))

    async def find_service_edge(
        self, organization_id: str, source_service_id: str, target_service_id: str
    ) -> ServiceEdge | None:
        for e in await self._service_edges(organization_id):
            if (e.source_service_id == source_service_id
                    and e.target_service_id == target_service_id):
                return e
        return None

    async def get_edge_row(
        self, organization_id: str, edge_id: str
    ) -> KnowledgeGraphEdge | None:
        stmt = select(KnowledgeGraphEdge).where(
            KnowledgeGraphEdge.id == edge_id,
            KnowledgeGraphEdge.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def service_adjacency(self, organization_id: str) -> GraphAdjacency:
        """Build the service-topology adjacency for the org (O(V+E))."""
        edges = await self._service_edges(organization_id)
        return GraphAdjacency([(e.source_service_id, e.target_service_id) for e in edges])

    # ----------------------------------------------------------- node helpers
    async def _service_node_ids(self, organization_id: str) -> set[str]:
        """All service node ids for the org (read-through cached)."""
        import time

        from app.observability import metrics
        from app.redis import cache

        ns = graph_cache_namespace(organization_id)
        started = time.perf_counter()
        cached = await cache.versioned_get(ns, "service_nodes")
        if cached is not None:
            metrics.observe_graph_traversal("load_service_nodes",
                                            time.perf_counter() - started, cache="hit")
            return set(cached)
        rows = await self.graph_repo.list_nodes(organization_id)
        ids = {service_id_from_key(n.node_key) for n in rows if is_service_key(n.node_key)}
        metrics.observe_graph_traversal("load_service_nodes",
                                        time.perf_counter() - started, cache="miss")
        try:
            await cache.versioned_set(ns, "service_nodes", value=sorted(ids),
                                      ttl=settings.GRAPH_CACHE_TTL_SECONDS)
        except Exception:  # pragma: no cover - cache must not break reads
            pass
        return ids

    # ----------------------------------------------- cached traversals (Sprint 62B)
    async def _cached_traversal(self, organization_id: str, op: str, node: str):
        """Read-through cache for per-node traversal results (blast/deps)."""
        import time

        from app.observability import metrics
        from app.redis import cache

        ns = graph_cache_namespace(organization_id)
        started = time.perf_counter()
        cached = await cache.versioned_get(ns, op, node)
        if cached is not None:
            metrics.observe_graph_traversal(op, time.perf_counter() - started, cache="hit")
            return list(cached)
        adj = await self.service_adjacency(organization_id)
        if op == "blast_radius":
            result = sorted(adj.impact_radius(node))
        elif op == "downstream":
            result = sorted(adj.downstream(node))
        elif op == "upstream":
            result = sorted(adj.upstream(node))
        else:  # pragma: no cover - guarded by callers
            result = []
        metrics.observe_graph_traversal(op, time.perf_counter() - started, cache="miss")
        try:
            await cache.versioned_set(ns, op, node, value=result,
                                      ttl=settings.GRAPH_CACHE_TTL_SECONDS)
        except Exception:  # pragma: no cover - cache must not break reads
            pass
        return result

    async def blast_radius(self, organization_id: str, service_id: str) -> list[str]:
        """Transitive dependents impacted by a failure on ``service_id`` (cached)."""
        return await self._cached_traversal(organization_id, "blast_radius", service_id)

    async def downstream_dependencies(self, organization_id: str, service_id: str) -> list[str]:
        """Transitive downstream dependencies of ``service_id`` (cached)."""
        return await self._cached_traversal(organization_id, "downstream", service_id)

    async def cached_shortest_path(
        self, organization_id: str, source: str, target: str
    ) -> list[str] | None:
        import time

        from app.observability import metrics
        from app.redis import cache

        ns = graph_cache_namespace(organization_id)
        started = time.perf_counter()
        suffix = f"{source}->{target}"
        cached = await cache.versioned_get(ns, "shortest_path", suffix)
        if cached is not None:
            metrics.observe_graph_traversal("shortest_path",
                                            time.perf_counter() - started, cache="hit")
            return list(cached) if cached else None
        adj = await self.service_adjacency(organization_id)
        path = adj.shortest_path(source, target)
        metrics.observe_graph_traversal("shortest_path",
                                        time.perf_counter() - started, cache="miss")
        try:
            await cache.versioned_set(ns, "shortest_path", suffix, value=path or [],
                                      ttl=settings.GRAPH_CACHE_TTL_SECONDS)
        except Exception:  # pragma: no cover - cache must not break reads
            pass
        return path

    # --------------------------------------------------- analytics + integrity
    async def find_orphans(self, organization_id: str) -> list[str]:
        """Service nodes that participate in no dependency edge (in or out)."""
        adj = await self.service_adjacency(organization_id)
        connected = set(adj.out_edges) | set(adj.in_edges)
        nodes = await self._service_node_ids(organization_id)
        return sorted(nodes - connected)

    async def find_cycle(self, organization_id: str) -> bool:
        adj = await self.service_adjacency(organization_id)
        return adj.has_cycle()

    async def analytics(self, organization_id: str) -> dict:
        """Graph health summary (read-through cached): sizes, cycles, orphans."""
        from app.redis import cache

        ns = graph_cache_namespace(organization_id)
        cached = await cache.versioned_get(ns, "analytics")
        if cached is not None:
            return cached
        adj = await self.service_adjacency(organization_id)
        nodes = await self._service_node_ids(organization_id)
        edge_count = sum(len(v) for v in adj.out_edges.values())
        connected = set(adj.out_edges) | set(adj.in_edges)
        orphans = sorted(nodes - connected)
        result = {
            "organization_id": organization_id,
            "nodes": len(nodes),
            "edges": edge_count,
            "has_cycle": adj.has_cycle(),
            "orphan_count": len(orphans),
            "orphans": orphans[:100],
            "critical_path_length": len(adj.critical_path()),
            "max_out_degree": max((len(v) for v in adj.out_edges.values()), default=0),
            "max_in_degree": max((len(v) for v in adj.in_edges.values()), default=0),
        }
        try:
            await cache.versioned_set(ns, "analytics", value=result,
                                      ttl=settings.GRAPH_CACHE_TTL_SECONDS)
        except Exception:  # pragma: no cover - cache must not break reads
            pass
        return result
