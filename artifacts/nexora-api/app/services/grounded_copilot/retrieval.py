"""RAG retrieval over the organization's reliability records.

A per-request semantic corpus is assembled from the org's most recent incident
investigations (rich free-text: title, summary, root cause, recommendations,
suspected trigger). The query and corpus are embedded with the shared
``EmbeddingService`` (real embeddings when ``OPENAI_API_KEY`` is set, otherwise a
deterministic offline-hash embedding) and ranked by cosine similarity.

This is real retrieval-augmented generation without a persistent vector store:
it is bounded (``COPILOT_RAG_CORPUS_LIMIT``) and fully offline-testable.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.repositories.incident import IncidentInvestigationRepository
from app.services.embeddings import EmbeddingService, cosine_similarity


@dataclass
class RetrievedChunk:
    source: str
    id: str
    label: str
    text: str
    score: float

    def as_citation(self) -> dict:
        return {
            "source": self.source,
            "id": self.id,
            "label": self.label,
            "detail": None,
        }


def _investigation_text(inv) -> str:
    parts = [
        getattr(inv, "title", None),
        getattr(inv, "summary", None),
        getattr(inv, "root_cause", None),
        getattr(inv, "suspected_trigger", None),
        getattr(inv, "recommendations", None),
    ]
    return "\n".join(p for p in parts if p)


class KnowledgeRetriever:
    """Embeds and ranks the org's reliability corpus against a query."""

    def __init__(self, session):
        self.session = session
        self.inv_repo = IncidentInvestigationRepository(session)
        self.embedder = EmbeddingService()

    @property
    def provider(self) -> str:
        return self.embedder.provider

    async def _build_corpus(self, organization_id: str) -> list[tuple[str, str, str]]:
        """Return (id, label, text) tuples for the org's recent incidents."""
        rows, _ = await self.inv_repo.list_for_org(
            organization_id, offset=0, limit=settings.COPILOT_RAG_CORPUS_LIMIT
        )
        corpus: list[tuple[str, str, str]] = []
        for inv in rows:
            text = _investigation_text(inv)
            if text.strip():
                corpus.append((inv.id, getattr(inv, "title", "Incident"), text))
        return corpus

    async def retrieve(
        self, organization_id: str, query: str, *, top_k: int | None = None
    ) -> list[RetrievedChunk]:
        top_k = top_k or settings.COPILOT_RAG_TOP_K
        corpus = await self._build_corpus(organization_id)
        if not corpus:
            return []

        query_vec = await self.embedder.embed_query(query)
        doc_vecs = await self.embedder.embed_texts([text for _, _, text in corpus])

        scored: list[RetrievedChunk] = []
        for (doc_id, label, text), vec in zip(corpus, doc_vecs, strict=False):
            score = cosine_similarity(query_vec, vec)
            scored.append(
                RetrievedChunk(
                    source="incident",
                    id=doc_id,
                    label=label,
                    text=text,
                    score=score,
                )
            )
        scored.sort(key=lambda c: c.score, reverse=True)
        # Only keep chunks with a positive similarity signal.
        return [c for c in scored if c.score > 0.0][:top_k]
