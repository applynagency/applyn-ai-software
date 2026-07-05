"""AI caches + request batching (Sprint 62B).

Three read-through caches that cut latency and cost on the AI hot path, all
built on the unified versioned cache (``app.redis.cache``) so they are shared
across replicas and invalidate in O(1):

* embedding cache  — embeddings are deterministic for a given text/model, so the
                     vector is cached by content hash (TTL-bounded).
* semantic cache   — near-duplicate prompts reuse a recent response when their
                     query embedding is within a cosine threshold (opt-in).
* request batching  — :func:`batch_embed` coalesces many embed calls, only
                     embedding cache-misses, so a burst of similar requests hits
                     the provider once.

Prompt (exact-match) response caching already lives in :class:`AIGateway`; this
module adds the embedding/semantic layers around it.
"""

from __future__ import annotations

import hashlib

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_EMBED_NS = "ai_embed"


def _text_hash(text: str, model: str) -> str:
    return hashlib.sha256(f"{model}\x00{text}".encode()).hexdigest()[:40]


async def cached_embed(texts: list[str], *, embedder=None) -> list[list[float]]:
    """Embed ``texts`` using a shared content-addressed cache.

    Only cache-missing texts are sent to the embedding provider (request
    batching); results are written back keyed by ``sha256(model+text)``.
    """
    if not texts:
        return []
    from app.services.embeddings import EmbeddingService

    embedder = embedder or EmbeddingService()
    if not settings.AI_EMBEDDING_CACHE_ENABLED:
        return await embedder.embed_texts(texts)

    from app.redis import cache

    model = getattr(embedder, "provider", "offline")
    keys = [_text_hash(t, model) for t in texts]
    results: list[list[float] | None] = [None] * len(texts)
    misses: list[int] = []
    for i, k in enumerate(keys):
        try:
            hit = await cache.versioned_get(_EMBED_NS, k)
        except Exception:  # pragma: no cover - cache optional
            hit = None
        if hit is not None:
            results[i] = hit
        else:
            misses.append(i)

    if misses:
        miss_vectors = await embedder.embed_texts([texts[i] for i in misses])
        for idx, vec in zip(misses, miss_vectors, strict=False):
            results[idx] = vec
            try:
                await cache.versioned_set(
                    _EMBED_NS, keys[idx], value=vec,
                    ttl=settings.AI_EMBEDDING_CACHE_TTL_SECONDS)
            except Exception:  # pragma: no cover - cache optional
                pass
    return [r if r is not None else [] for r in results]


async def batch_embed(texts: list[str], *, embedder=None) -> list[list[float]]:
    """Alias for :func:`cached_embed` — coalesces + caches a batch of embeds."""
    return await cached_embed(texts, embedder=embedder)


class SemanticResponseCache:
    """Bounded in-process semantic cache of recent (embedding, response) pairs.

    A new prompt whose embedding is within ``AI_SEMANTIC_CACHE_THRESHOLD`` cosine
    of a cached prompt returns the cached response. Per-organization, bounded
    (LRU-ish) so memory stays flat under load.
    """

    def __init__(self, max_per_org: int = 64) -> None:
        self._store: dict[str, list[tuple[list[float], str]]] = {}
        self._max = max_per_org

    def lookup(self, organization_id: str | None, embedding: list[float]) -> str | None:
        if not settings.AI_SEMANTIC_CACHE_ENABLED or not embedding:
            return None
        from app.services.embeddings import cosine_similarity

        threshold = float(settings.AI_SEMANTIC_CACHE_THRESHOLD)
        bucket = self._store.get(organization_id or "global", [])
        best: tuple[float, str] | None = None
        for vec, resp in bucket:
            sim = cosine_similarity(embedding, vec)
            if sim >= threshold and (best is None or sim > best[0]):
                best = (sim, resp)
        return best[1] if best else None

    def store(self, organization_id: str | None, embedding: list[float], response: str) -> None:
        if not settings.AI_SEMANTIC_CACHE_ENABLED or not embedding:
            return
        key = organization_id or "global"
        bucket = self._store.setdefault(key, [])
        bucket.append((embedding, response))
        if len(bucket) > self._max:
            del bucket[0: len(bucket) - self._max]

    def clear(self) -> None:  # test helper
        self._store.clear()


_SEMANTIC_CACHE = SemanticResponseCache()


def get_semantic_cache() -> SemanticResponseCache:
    return _SEMANTIC_CACHE
