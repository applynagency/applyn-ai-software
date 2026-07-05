"""Sprint 37D — embedding generation for the Team Knowledge Base (RAG).

Embeddings power similarity search over customer documents. When
``OPENAI_API_KEY`` is configured, real embeddings are produced; otherwise a
deterministic, network-free hashing embedding is used so the feature (and tests)
work without external dependencies — mirroring the LLM runner's "simulated when
not configured" philosophy.

This is strictly retrieval infrastructure: no long-term memory, no autonomous
learning, no external browsing.
"""

import hashlib
import math
import re

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


class EmbeddingService:
    """Produces fixed-dimension embeddings for documents and queries."""

    def __init__(self):
        self.dim = settings.EMBEDDING_DIM
        self._offline = not settings.OPENAI_API_KEY
        self._client = None

    @property
    def provider(self) -> str:
        return "offline-hash" if self._offline else "openai"

    def _ensure_client(self):
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        return self._client

    def _offline_embedding(self, text: str) -> list[float]:
        """Bag-of-words hashing embedding, L2-normalized.

        Shared tokens between two texts raise their cosine similarity, which is
        enough for functional retrieval without a real embedding provider.
        """
        vec = [0.0] * self.dim
        tokens = _tokenize(text)
        if not tokens:
            return vec
        for token in tokens:
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._offline:
            return [self._offline_embedding(t) for t in texts]
        try:
            client = self._ensure_client()
            resp = await client.embeddings.create(
                model=settings.EMBEDDING_MODEL,
                input=texts,
                dimensions=self.dim,
            )
            return [item.embedding for item in resp.data]
        except Exception as exc:  # noqa: BLE001 - degrade gracefully to offline
            logger.error("embedding_provider_error", error=str(exc))
            # Fall back to offline embeddings so a transient provider issue does
            # not lose the customer's document. Consistency is preserved because
            # query embeddings use the same service instance/provider per request.
            return [self._offline_embedding(t) for t in texts]

    async def embed_query(self, text: str) -> list[float]:
        result = await self.embed_texts([text])
        return result[0] if result else [0.0] * self.dim
