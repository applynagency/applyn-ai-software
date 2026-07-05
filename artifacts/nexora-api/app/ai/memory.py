"""Long-term memory (Sprint 61D).

Four scopes — semantic, episodic, organization, user — stored in one table with
optional embeddings for semantic recall. Embedding generation is provider
independent (reuses :class:`EmbeddingService`, which is OpenAI or offline-hash),
so memory works with or without an embedding provider configured.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.ai_platform import AIMemoryEntry, MemoryScope
from app.services.embeddings import EmbeddingService, cosine_similarity


class MemoryService:
    def __init__(self, session: AsyncSession, embedder: EmbeddingService | None = None) -> None:
        self.session = session
        self.embedder = embedder or EmbeddingService()

    async def remember(
        self, *, organization_id: str, content: str,
        scope: MemoryScope | str = MemoryScope.SEMANTIC, namespace: str = "default",
        user_id: str | None = None, importance: float = 0.5,
        metadata: dict | None = None, embed: bool = True,
    ) -> AIMemoryEntry:
        scope_value = scope.value if isinstance(scope, MemoryScope) else scope
        embedding = None
        provider = None
        if embed:
            embedding = await self.embedder.embed_query(content)
            provider = self.embedder.provider
        entry = AIMemoryEntry(
            organization_id=organization_id, user_id=user_id, scope=scope_value,
            namespace=namespace, content=content, embedding=embedding,
            embedding_provider=provider, importance=importance,
            entry_metadata=metadata,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def recall(
        self, *, organization_id: str, query: str,
        scope: MemoryScope | str | None = None, namespace: str | None = None,
        user_id: str | None = None, top_k: int | None = None,
    ) -> list[dict]:
        top_k = top_k or settings.AI_MEMORY_TOP_K
        stmt = select(AIMemoryEntry).where(AIMemoryEntry.organization_id == organization_id)
        if scope is not None:
            scope_value = scope.value if isinstance(scope, MemoryScope) else scope
            stmt = stmt.where(AIMemoryEntry.scope == scope_value)
        if namespace is not None:
            stmt = stmt.where(AIMemoryEntry.namespace == namespace)
        if user_id is not None:
            stmt = stmt.where(AIMemoryEntry.user_id == user_id)
        rows = list((await self.session.execute(stmt)).scalars().all())
        if not rows:
            return []
        query_vec = await self.embedder.embed_query(query)
        scored = []
        for row in rows:
            sim = cosine_similarity(query_vec, row.embedding or []) if row.embedding else 0.0
            # Blend similarity with stored importance for ranking.
            score = sim + settings.MEMORY_IMPORTANCE_WEIGHT * row.importance
            scored.append((score, sim, row))
        scored.sort(key=lambda t: t[0], reverse=True)
        out = []
        for score, sim, row in scored[:top_k]:
            out.append({
                "id": row.id, "scope": row.scope, "namespace": row.namespace,
                "content": row.content, "similarity": round(sim, 4),
                "importance": row.importance, "metadata": row.entry_metadata,
            })
        return out

    async def list_entries(
        self, *, organization_id: str, scope: MemoryScope | str | None = None,
        limit: int = 100,
    ) -> list[AIMemoryEntry]:
        stmt = select(AIMemoryEntry).where(AIMemoryEntry.organization_id == organization_id)
        if scope is not None:
            scope_value = scope.value if isinstance(scope, MemoryScope) else scope
            stmt = stmt.where(AIMemoryEntry.scope == scope_value)
        stmt = stmt.order_by(AIMemoryEntry.created_at.desc()).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def forget(self, *, organization_id: str, entry_id: str) -> bool:
        entry = await self.session.get(AIMemoryEntry, entry_id)
        if entry is None or entry.organization_id != organization_id:
            return False
        await self.session.delete(entry)
        await self.session.flush()
        return True
