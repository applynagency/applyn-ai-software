"""Global search platform (Sprint 62A).

ONE search service across every core entity (incidents, services, assets,
workflows, AI conversations, AI agents, users, runbooks/documentation).

Each entity is exposed via a registered :class:`SearchProvider`. Results are
merged and ranked (lexical relevance + recency, with an optional semantic
re-rank using the embedding service). Supports type filters, pagination and
autocomplete. Providers are defensive: a failing provider never breaks search.
"""

from __future__ import annotations

import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

logger = get_logger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_PHRASE_RE = re.compile(r'"([^"]+)"')

# Ranking profiles: per-field + recency weights. ``default`` balances title and
# body; ``title_boost`` favours exact title matches; ``recent`` favours recency.
RANKING_PROFILES: dict[str, dict[str, float]] = {
    "default": {"title": 1.0, "body": 0.4, "keywords": 0.6, "recency": 0.2},
    "title_boost": {"title": 1.5, "body": 0.2, "keywords": 0.5, "recency": 0.1},
    "recent": {"title": 0.8, "body": 0.3, "keywords": 0.4, "recency": 0.6},
}

# Synonym dictionary — each token maps to additional query terms (bidirectional
# is achieved by listing both directions). Kept small + domain-specific.
SYNONYMS: dict[str, list[str]] = {
    "db": ["database", "postgres", "sql"],
    "database": ["db", "postgres"],
    "k8s": ["kubernetes"],
    "kubernetes": ["k8s"],
    "vm": ["virtual machine", "instance"],
    "incident": ["outage", "issue"],
    "outage": ["incident", "downtime"],
    "svc": ["service"],
    "service": ["svc"],
    "auth": ["authentication", "login"],
    "perf": ["performance", "latency"],
}


def normalize_query(query: str) -> str:
    return " ".join(_TOKEN_RE.findall((query or "").lower()))


def expand_synonyms(tokens: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for tok in tokens:
        for term in (tok, *SYNONYMS.get(tok, [])):
            if term not in seen:
                seen.add(term)
                out.append(term)
    return out


def _levenshtein(a: str, b: str) -> int:
    """Iterative edit distance (bounded inputs: single tokens)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _typo_match(token: str, candidate: str) -> bool:
    """True when ``candidate`` is within an edit distance allowed for its length."""
    if token == candidate:
        return True
    if candidate.startswith(token) or token in candidate:
        return True
    # Allow 1 edit for short tokens, 2 for longer ones.
    allowed = 1 if len(token) <= 5 else 2
    return _levenshtein(token, candidate) <= allowed


@dataclass
class SearchHit:
    type: str
    id: str
    title: str
    snippet: str = ""
    url: str | None = None
    organization_id: str | None = None
    created_at: datetime | None = None
    score: float = 0.0
    extra: dict = field(default_factory=dict)


ProviderFn = Callable[[AsyncSession, str, str | None, int], Awaitable[list[SearchHit]]]
_PROVIDERS: dict[str, ProviderFn] = {}


def register_provider(entity_type: str, fn: ProviderFn) -> None:
    _PROVIDERS[entity_type] = fn


def available_types() -> list[str]:
    return sorted(_PROVIDERS.keys())


def _match(query: str, *columns):
    """Build an OR condition matching the full phrase OR any token in any column."""
    tokens = [query.strip(), *query.split()]
    seen: set[str] = set()
    conds = []
    for tok in tokens:
        tok = tok.strip()
        if not tok or tok.lower() in seen:
            continue
        seen.add(tok.lower())
        for col in columns:
            conds.append(col.ilike(f"%{tok}%"))
    return or_(*conds)


def _lexical_score(query: str, *texts: str | None) -> float:
    q = (query or "").strip().lower()
    if not q:
        return 0.0
    best = 0.0
    q_tokens = set(q.split())
    for text in texts:
        if not text:
            continue
        t = text.lower()
        if t == q:
            best = max(best, 1.0)
        elif t.startswith(q):
            best = max(best, 0.85)
        elif q in t:
            best = max(best, 0.6)
        if q_tokens:
            overlap = len(q_tokens & set(t.split())) / len(q_tokens)
            best = max(best, 0.5 * overlap)
    return best


# --------------------------------------------------------------------------- #
# Built-in providers
# --------------------------------------------------------------------------- #
async def _search_incidents(session, query, org_id, limit):
    from app.models.incident import IncidentInvestigation as M
    stmt = select(M).where(_match(query, M.title, M.summary))
    if org_id:
        stmt = stmt.where(M.organization_id == org_id)
    rows = (await session.execute(stmt.limit(limit))).scalars().all()
    return [SearchHit(type="incident", id=r.id, title=r.title or "Incident",
                      snippet=(r.summary or "")[:200], url=f"/incidents/{r.id}",
                      organization_id=r.organization_id, created_at=r.created_at) for r in rows]


async def _search_services(session, query, org_id, limit):
    from app.models.universal_discovery import KnowledgeGraphNode as M
    stmt = select(M).where(_match(query, M.name, M.display_name))
    if org_id:
        stmt = stmt.where(M.organization_id == org_id)
    rows = (await session.execute(stmt.limit(limit))).scalars().all()
    return [SearchHit(type="service", id=r.id, title=r.display_name or r.name or r.node_key,
                      snippet=(r.node_type or ""), url=f"/graph/nodes/{r.id}",
                      organization_id=r.organization_id, created_at=r.created_at) for r in rows]


async def _search_assets(session, query, org_id, limit):
    from app.models.universal_discovery import DiscoveredAsset as M
    stmt = select(M).where(_match(query, M.resource_name, M.display_name))
    if org_id:
        stmt = stmt.where(M.organization_id == org_id)
    rows = (await session.execute(stmt.limit(limit))).scalars().all()
    return [SearchHit(type="asset", id=r.id, title=r.display_name or r.resource_name,
                      snippet=f"{r.provider}/{r.resource_type}", url=f"/assets/{r.id}",
                      organization_id=r.organization_id, created_at=r.created_at) for r in rows]


async def _search_runbooks(session, query, org_id, limit):
    from app.models.runbook import Runbook as M
    stmt = select(M).where(_match(query, M.title, M.summary, M.search_text))
    if org_id:
        stmt = stmt.where(M.organization_id == org_id)
    rows = (await session.execute(stmt.limit(limit))).scalars().all()
    return [SearchHit(type="runbook", id=r.id, title=r.title,
                      snippet=(r.summary or "")[:200], url=f"/runbooks/{r.id}",
                      organization_id=r.organization_id, created_at=r.created_at) for r in rows]


async def _search_workflows(session, query, org_id, limit):
    from app.models.ai_team import AITeamWorkflow as M
    stmt = select(M).where(_match(query, M.name, M.description))
    if org_id:
        stmt = stmt.where(M.organization_id == org_id)
    rows = (await session.execute(stmt.limit(limit))).scalars().all()
    return [SearchHit(type="workflow", id=r.id, title=r.name,
                      snippet=(r.description or "")[:200], url=f"/workflows/{r.id}",
                      organization_id=r.organization_id, created_at=r.created_at) for r in rows]


async def _search_ai_agents(session, query, org_id, limit):
    from app.models.ai_team import AITeamAgent as M
    stmt = select(M).where(_match(query, M.name, M.role, M.description))
    if org_id:
        stmt = stmt.where(M.organization_id == org_id)
    rows = (await session.execute(stmt.limit(limit))).scalars().all()
    return [SearchHit(type="ai_agent", id=r.id, title=r.name, snippet=r.role or "",
                      url=f"/ai-agents/{r.id}", organization_id=r.organization_id,
                      created_at=r.created_at) for r in rows]


async def _search_ai_conversations(session, query, org_id, limit):
    from app.models.ai_team import AITeamAgentRun as M
    stmt = select(M).where(_match(query, M.prompt, M.response))
    if org_id:
        stmt = stmt.where(M.organization_id == org_id)
    rows = (await session.execute(stmt.limit(limit))).scalars().all()
    return [SearchHit(type="ai_conversation", id=r.id, title=(r.prompt or "")[:80],
                      snippet=(r.response or "")[:200], url=f"/ai-runs/{r.id}",
                      organization_id=r.organization_id, created_at=r.created_at) for r in rows]


async def _search_users(session, query, org_id, limit):
    from app.models.organization import OrganizationMember
    from app.models.user import User
    stmt = select(User).where(_match(query, User.email, User.username, User.full_name))
    if org_id:
        stmt = stmt.join(OrganizationMember, OrganizationMember.user_id == User.id).where(
            OrganizationMember.organization_id == org_id)
    rows = (await session.execute(stmt.limit(limit))).scalars().all()
    return [SearchHit(type="user", id=r.id, title=r.full_name or r.username or r.email,
                      snippet=r.email, url=f"/users/{r.id}",
                      organization_id=org_id, created_at=r.created_at) for r in rows]


register_provider("incident", _search_incidents)
register_provider("service", _search_services)
register_provider("asset", _search_assets)
register_provider("runbook", _search_runbooks)
register_provider("workflow", _search_workflows)
register_provider("ai_agent", _search_ai_agents)
register_provider("ai_conversation", _search_ai_conversations)
register_provider("user", _search_users)


# --------------------------------------------------------------------------- #
# Search service
# --------------------------------------------------------------------------- #
def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


# --------------------------------------------------------------------------- #
# Incremental index + indexables
# --------------------------------------------------------------------------- #
# An indexable lists source rows for an org and maps them to index-doc dicts.
IndexableFn = Callable[[AsyncSession, str | None, int], Awaitable[list[dict]]]
_INDEXABLES: dict[str, IndexableFn] = {}


def register_indexable(entity_type: str, fn: IndexableFn) -> None:
    _INDEXABLES[entity_type] = fn


def indexable_types() -> list[str]:
    return sorted(_INDEXABLES.keys())


async def _idx_incidents(session, org_id, limit):
    from app.models.incident import IncidentInvestigation as M
    stmt = select(M)
    if org_id:
        stmt = stmt.where(M.organization_id == org_id)
    rows = (await session.execute(stmt.limit(limit))).scalars().all()
    return [{"entity_id": r.id, "organization_id": r.organization_id,
             "title": r.title or "Incident", "body": (r.summary or ""),
             "url": f"/incidents/{r.id}", "weight": 1.2,
             "source_updated_at": r.updated_at} for r in rows]


async def _idx_services(session, org_id, limit):
    from app.models.universal_discovery import KnowledgeGraphNode as M
    stmt = select(M)
    if org_id:
        stmt = stmt.where(M.organization_id == org_id)
    rows = (await session.execute(stmt.limit(limit))).scalars().all()
    return [{"entity_id": r.id, "organization_id": r.organization_id,
             "title": r.display_name or r.name or r.node_key, "body": (r.node_type or ""),
             "url": f"/graph/nodes/{r.id}", "weight": 1.0,
             "source_updated_at": r.updated_at} for r in rows]


async def _idx_runbooks(session, org_id, limit):
    from app.models.runbook import Runbook as M
    stmt = select(M)
    if org_id:
        stmt = stmt.where(M.organization_id == org_id)
    rows = (await session.execute(stmt.limit(limit))).scalars().all()
    return [{"entity_id": r.id, "organization_id": r.organization_id,
             "title": r.title, "body": (r.summary or ""),
             "url": f"/runbooks/{r.id}", "weight": 1.0,
             "source_updated_at": r.updated_at} for r in rows]


async def _idx_workflows(session, org_id, limit):
    from app.models.ai_team import AITeamWorkflow as M
    stmt = select(M)
    if org_id:
        stmt = stmt.where(M.organization_id == org_id)
    rows = (await session.execute(stmt.limit(limit))).scalars().all()
    return [{"entity_id": r.id, "organization_id": r.organization_id,
             "title": r.name, "body": (r.description or ""),
             "url": f"/workflows/{r.id}", "weight": 1.0,
             "source_updated_at": r.updated_at} for r in rows]


async def _idx_ai_agents(session, org_id, limit):
    from app.models.ai_team import AITeamAgent as M
    stmt = select(M)
    if org_id:
        stmt = stmt.where(M.organization_id == org_id)
    rows = (await session.execute(stmt.limit(limit))).scalars().all()
    return [{"entity_id": r.id, "organization_id": r.organization_id,
             "title": r.name, "body": f"{r.role or ''} {r.description or ''}".strip(),
             "url": f"/ai-agents/{r.id}", "weight": 1.0,
             "source_updated_at": r.updated_at} for r in rows]


register_indexable("incident", _idx_incidents)
register_indexable("service", _idx_services)
register_indexable("runbook", _idx_runbooks)
register_indexable("workflow", _idx_workflows)
register_indexable("ai_agent", _idx_ai_agents)


class SearchIndexer:
    """Maintains the ``search_documents`` index incrementally (no full rebuilds).

    Entities call :meth:`index_entity`/:meth:`remove_entity` as they change; a
    background cron calls :meth:`reindex_org` to reconcile drift.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def index_entity(
        self, *, entity_type: str, entity_id: str, organization_id: str | None,
        title: str, body: str = "", url: str | None = None, weight: float = 1.0,
        source_updated_at: datetime | None = None,
    ) -> None:
        from app.database.base import utcnow
        from app.models.platform_core import SearchDocument

        keywords = normalize_query(f"{title} {body}")
        existing = (await self.session.execute(
            select(SearchDocument).where(
                SearchDocument.entity_type == entity_type,
                SearchDocument.entity_id == entity_id,
            ))).scalar_one_or_none()
        if existing is None:
            existing = SearchDocument(entity_type=entity_type, entity_id=entity_id)
            self.session.add(existing)
        existing.organization_id = organization_id
        existing.title = title or ""
        existing.body = (body or "")[:8000]
        existing.keywords = keywords[:8000]
        existing.url = url
        existing.weight = weight
        existing.source_updated_at = source_updated_at
        existing.indexed_at = utcnow()
        await self.session.flush()

    async def remove_entity(self, *, entity_type: str, entity_id: str) -> None:
        from app.models.platform_core import SearchDocument

        row = (await self.session.execute(
            select(SearchDocument).where(
                SearchDocument.entity_type == entity_type,
                SearchDocument.entity_id == entity_id,
            ))).scalar_one_or_none()
        if row is not None:
            await self.session.delete(row)
            await self.session.flush()

    async def reindex_org(
        self, organization_id: str | None, *, types: list[str] | None = None,
        per_type: int = 1000,
    ) -> int:
        selected = types or indexable_types()
        count = 0
        for entity_type in selected:
            fn = _INDEXABLES.get(entity_type)
            if fn is None:
                continue
            try:
                docs = await fn(self.session, organization_id, per_type)
            except Exception as exc:  # noqa: BLE001 - one bad source must not abort
                logger.warning("reindex_source_failed", entity_type=entity_type, error=str(exc))
                continue
            for doc in docs:
                await self.index_entity(entity_type=entity_type, **doc)
                count += 1
        return count


class SearchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _gather(self, query: str, organization_id: str | None,
                      types: list[str] | None, per_provider: int) -> list[SearchHit]:
        selected = types or available_types()
        hits: list[SearchHit] = []
        for entity_type in selected:
            provider = _PROVIDERS.get(entity_type)
            if provider is None:
                continue
            try:
                hits.extend(await provider(self.session, query, organization_id, per_provider))
            except Exception as exc:  # noqa: BLE001 - a bad provider must not break search
                logger.warning("search_provider_failed", entity_type=entity_type, error=str(exc))
        return hits

    async def search(
        self,
        query: str,
        *,
        organization_id: str | None = None,
        types: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
        semantic: bool = False,
        profile: str = "default",
        user_id: str | None = None,
        use_index: bool | None = None,
    ) -> dict:
        from app.core.config import settings

        query = (query or "").strip()
        if not query:
            return {"query": query, "total": 0, "results": []}

        started = time.perf_counter()
        backend = "live"
        per_provider = max(limit + offset, 10)

        # Prefer the incremental index when enabled and populated; otherwise fall
        # back to the live providers so search always works.
        index_hits: list[SearchHit] | None = None
        if use_index is not False and getattr(settings, "SEARCH_INDEX_ENABLED", True):
            index_hits = await self._index_search(query, organization_id, types,
                                                  per_provider, profile)
        if index_hits:
            hits = index_hits
            backend = "index"
        else:
            hits = await self._gather(query, organization_id, types, per_provider)
            for hit in hits:
                hit.score = _lexical_score(query, hit.title, hit.snippet)

        if semantic and hits:
            try:
                from app.services.embeddings import EmbeddingService

                embedder = EmbeddingService()
                q_vec = (await embedder.embed_texts([query]))[0]
                titles = [h.title or "" for h in hits]
                vecs = await embedder.embed_texts(titles)
                for hit, vec in zip(hits, vecs, strict=False):
                    hit.score = 0.5 * hit.score + 0.5 * _cosine(q_vec, vec)
            except Exception as exc:  # noqa: BLE001 - degrade to lexical
                logger.warning("search_semantic_failed", error=str(exc))

        hits.sort(key=lambda h: (h.score, h.created_at or datetime.min), reverse=True)
        total = len(hits)
        page = hits[offset:offset + limit]
        took_ms = (time.perf_counter() - started) * 1000.0

        await self._log_query(query, organization_id, user_id, total, took_ms, profile)
        try:
            from app.observability import metrics

            metrics.record_search_query(backend, "hit" if total else "empty",
                                        took_ms / 1000.0)
        except Exception:  # pragma: no cover
            pass

        return {
            "query": query,
            "backend": backend,
            "profile": profile,
            "took_ms": round(took_ms, 2),
            "total": total,
            "results": [
                {
                    "type": h.type, "id": h.id, "title": h.title, "snippet": h.snippet,
                    "url": h.url, "score": round(h.score, 4),
                    "organization_id": h.organization_id,
                } for h in page
            ],
        }

    async def _index_search(
        self, query: str, organization_id: str | None, types: list[str] | None,
        limit: int, profile: str,
    ) -> list[SearchHit]:
        """Search the incremental index with synonyms, phrase + typo tolerance."""
        from app.core.config import settings
        from app.models.platform_core import SearchDocument

        phrases = [p.strip().lower() for p in _PHRASE_RE.findall(query) if p.strip()]
        tokens = normalize_query(query).split()
        if not tokens:
            return []
        expanded = expand_synonyms(tokens)

        stmt = select(SearchDocument)
        if organization_id is not None:
            stmt = stmt.where(SearchDocument.organization_id == organization_id)
        if types:
            stmt = stmt.where(SearchDocument.entity_type.in_(types))
        # Coarse DB filter: any token as a substring (keeps the candidate set small);
        # phrase/typo scoring is applied in Python below.
        conds = []
        for tok in expanded:
            conds.append(SearchDocument.keywords.ilike(f"%{tok}%"))
            conds.append(SearchDocument.title.ilike(f"%{tok}%"))
        if phrases:
            for ph in phrases:
                conds.append(SearchDocument.body.ilike(f"%{ph}%"))
                conds.append(SearchDocument.title.ilike(f"%{ph}%"))
        stmt = stmt.where(or_(*conds)).limit(limit * 5)
        rows = (await self.session.execute(stmt)).scalars().all()

        weights = RANKING_PROFILES.get(profile, RANKING_PROFILES["default"])
        typo = getattr(settings, "SEARCH_TYPO_TOLERANCE", True)
        hits: list[SearchHit] = []
        now = datetime.now(tz=None)
        for doc in rows:
            score = self._score_document(doc, tokens, expanded, phrases, weights, typo, now)
            if score <= 0:
                continue
            hits.append(SearchHit(
                type=doc.entity_type, id=doc.entity_id, title=doc.title,
                snippet=(doc.body or "")[:200], url=doc.url,
                organization_id=doc.organization_id, created_at=doc.indexed_at,
                score=score))
        return hits

    @staticmethod
    def _score_document(doc, tokens, expanded, phrases, weights, typo, now) -> float:
        title_l = (doc.title or "").lower()
        body_l = (doc.body or "").lower()
        kw_tokens = (doc.keywords or "").split()
        kw_set = set(kw_tokens)
        score = 0.0

        # Weighted field token coverage (with optional typo tolerance).
        matched = 0
        for tok in tokens:
            if tok in kw_set or tok in title_l:
                matched += 1
            elif typo and any(_typo_match(tok, k) for k in kw_tokens):
                matched += 0.6
        coverage = matched / max(1, len(tokens))
        score += weights["keywords"] * coverage

        # Title relevance.
        if title_l:
            joined = " ".join(tokens)
            if title_l == joined:
                score += weights["title"]
            elif title_l.startswith(joined):
                score += weights["title"] * 0.7
            elif any(t in title_l for t in expanded):
                score += weights["title"] * 0.4

        # Phrase search (exact ordered substring) is a strong signal.
        for ph in phrases:
            if ph in body_l or ph in title_l:
                score += weights["body"] + 0.5

        # Body partial.
        if any(t in body_l for t in tokens):
            score += weights["body"] * 0.3

        # Recency.
        if doc.indexed_at is not None:
            try:
                age_days = max(0.0, (now - doc.indexed_at.replace(tzinfo=None)).days)
                score += weights["recency"] * (1.0 / (1.0 + age_days))
            except Exception:  # pragma: no cover - defensive on tz
                pass

        return score * float(doc.weight or 1.0)

    async def _log_query(
        self, query: str, organization_id: str | None, user_id: str | None,
        total: int, took_ms: float, profile: str,
    ) -> None:
        from app.core.config import settings

        if not getattr(settings, "SEARCH_ANALYTICS_ENABLED", True):
            return
        try:
            from app.models.platform_core import SearchQueryLog

            self.session.add(SearchQueryLog(
                organization_id=organization_id, user_id=user_id,
                query=query[:500], normalized_query=normalize_query(query)[:500],
                results_count=total, took_ms=took_ms, profile=profile))
            await self.session.flush()
        except Exception as exc:  # noqa: BLE001 - analytics must not break search
            logger.warning("search_analytics_failed", error=str(exc))

    async def analytics(self, *, organization_id: str | None = None, days: int = 7,
                        limit: int = 20) -> dict:
        """Top queries + zero-result queries over the window."""
        from datetime import timedelta

        from sqlalchemy import func

        from app.database.base import utcnow
        from app.models.platform_core import SearchQueryLog

        since = utcnow() - timedelta(days=days)
        base = select(
            SearchQueryLog.normalized_query,
            func.count(SearchQueryLog.id),
            func.avg(SearchQueryLog.results_count),
            func.avg(SearchQueryLog.took_ms),
        ).where(SearchQueryLog.created_at >= since, SearchQueryLog.normalized_query != "")
        if organization_id is not None:
            base = base.where(SearchQueryLog.organization_id == organization_id)
        base = base.group_by(SearchQueryLog.normalized_query)

        top = (await self.session.execute(
            base.order_by(func.count(SearchQueryLog.id).desc()).limit(limit))).all()
        zero = (await self.session.execute(
            base.having(func.max(SearchQueryLog.results_count) == 0).limit(limit))).all()
        return {
            "window_days": days,
            "top_queries": [
                {"query": q, "count": int(c), "avg_results": round(float(ar or 0), 2),
                 "avg_took_ms": round(float(at or 0), 2)} for q, c, ar, at in top
            ],
            "zero_result_queries": [
                {"query": q, "count": int(c)} for q, c, _ar, _at in zero
            ],
        }

    async def autocomplete(
        self, prefix: str, *, organization_id: str | None = None,
        types: list[str] | None = None, limit: int = 10,
    ) -> list[dict]:
        prefix = (prefix or "").strip()
        if not prefix:
            return []
        hits = await self._gather(prefix, organization_id, types, limit)
        suggestions: list[dict] = []
        seen: set[str] = set()
        # Prefer prefix matches, then contains.
        for ranked in (True, False):
            for hit in hits:
                title = hit.title or ""
                key = f"{hit.type}:{title.lower()}"
                if key in seen or not title:
                    continue
                is_prefix = title.lower().startswith(prefix.lower())
                if is_prefix == ranked:
                    suggestions.append({"type": hit.type, "id": hit.id, "title": title})
                    seen.add(key)
                if len(suggestions) >= limit:
                    return suggestions
        return suggestions
