"""Grounded copilot orchestrator.

Pipeline (retrieve-then-read):

1. Memory     — replay prior conversation turns.
2. Tools      — invoke read-only tools: reliability evidence, knowledge graph,
                RAG over incidents. (Tool calls are recorded.)
3. Ground     — assemble an evidence-only prompt; the system prompt forbids
                using anything outside it.
4. Generate   — LLM answer with retry/backoff; deterministic fallback/offline.
5. Validate   — hallucination prevention (citations must reference retrieved
                records) + confidence scoring.
6. Persist    — store the turn (conversation history).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import structlog

from app.core.config import settings
from app.core.exceptions import ForbiddenError, NexoraException
from app.database.base import utcnow
from app.models.grounded_copilot import GroundedCopilotRole
from app.repositories.audit import AuditLogRepository
from app.repositories.grounded_copilot import (
    GroundedCopilotConversationRepository,
    GroundedCopilotMessageRepository,
)
from app.services.grounded_copilot import memory as memory_mod
from app.services.grounded_copilot.confidence import (
    build_allowed_set,
    score_confidence,
    validate_citations,
)
from app.services.grounded_copilot.evidence import EvidenceProvider
from app.services.grounded_copilot.knowledge_graph import KnowledgeGraphGrounder
from app.services.grounded_copilot.llm import GroundedLLMClient
from app.services.grounded_copilot.prompts import SYSTEM_PROMPT, build_user_prompt
from app.services.grounded_copilot.retrieval import KnowledgeRetriever
from app.tenancy.permissions import can_read_ai_teams

logger = structlog.get_logger(__name__)

SUGGESTED_QUESTIONS = [
    "What caused our most recent incident?",
    "Which service has the largest blast radius?",
    "Is it safe to deploy the payments service?",
    "What are our biggest reliability risks right now?",
    "Show incidents from the last 7 days.",
]


class _Evidence:
    """Aggregated grounding bundle for a single question."""

    def __init__(self):
        self.intent: str = "HELP"
        self.evidence_text: str = ""
        self.graph_facts: str = ""
        self.rag_text: str = ""
        self.citations: list[dict] = []
        self.sources: list[dict] = []
        self.tool_calls: list[dict] = []
        self.top_similarity: float = 0.0
        self.service: str | None = None


class GroundedCopilotEngine:
    def __init__(self, session):
        self.session = session
        self.conv_repo = GroundedCopilotConversationRepository(session)
        self.msg_repo = GroundedCopilotMessageRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.evidence = EvidenceProvider(session)
        self.retriever = KnowledgeRetriever(session)
        self.grapher = KnowledgeGraphGrounder(session)
        self.llm = GroundedLLMClient(session=session)

    # ------------------------------------------------------- authorization
    def _ensure_read(self, user, org_context) -> None:
        if not user.is_superuser and (
            not org_context.role or not can_read_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    # ----------------------------------------------------- conversations
    async def list_conversations(self, user, org_context):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        convs = await self.conv_repo.list_for_org(organization_id)
        out = []
        for c in convs:
            count = await self.msg_repo.count_for_conversation(c.id)
            out.append((c, count))
        return out

    async def get_conversation(self, user, org_context, conversation_id: str):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        conv = await self.conv_repo.get_for_org(conversation_id, organization_id)
        if conv is None:
            raise NexoraException("Conversation not found.", status_code=404)
        messages = await self.msg_repo.list_for_conversation(conversation_id, organization_id)
        return conv, messages

    async def _resolve_conversation(self, organization_id, user, req):
        if req.conversation_id:
            conv = await self.conv_repo.get_for_org(req.conversation_id, organization_id)
            if conv is None:
                raise NexoraException("Conversation not found.", status_code=404)
            return conv
        return await self.conv_repo.create(
            organization_id=organization_id,
            title=req.message[:60],
            created_by=user.id,
        )

    # ------------------------------------------------------------ gather
    async def _gather(self, organization_id: str, question: str, filters=None) -> _Evidence:
        ev = _Evidence()

        # Tool 1: authoritative reliability evidence (deterministic, cited).
        evidence = await self.evidence.gather_evidence(organization_id, question, filters=filters)
        ev.intent = evidence["intent"]
        ev.evidence_text = evidence["answer"] or ""
        ev.citations.extend(c.model_dump() for c in evidence["citations"])
        ev.service = getattr(evidence["filters"], "service", None)
        ev.tool_calls.append(
            {
                "tool": "search_reliability_data",
                "input": {"question": question},
                "ok": bool(ev.evidence_text),
            }
        )

        # Tool 2: knowledge-graph facts.
        graph = await self.grapher.ground(organization_id, ev.service)
        ev.graph_facts = graph.facts
        ev.citations.extend(graph.citations)
        ev.tool_calls.append(
            {
                "tool": "get_service_blast_radius",
                "input": {"service": ev.service},
                "ok": bool(graph.facts),
            }
        )

        # Tool 3: RAG over incident knowledge.
        chunks = await self.retriever.retrieve(organization_id, question)
        if chunks:
            ev.top_similarity = chunks[0].score
            rag_lines = []
            for c in chunks:
                snippet = c.text.strip().replace("\n", " ")
                if len(snippet) > 280:
                    snippet = snippet[:280] + "…"
                rag_lines.append(f"[incident:{c.id}] ({c.score:.2f}) {c.label}: {snippet}")
                ev.sources.append(
                    {"source": c.source, "id": c.id, "label": c.label, "score": round(c.score, 4)}
                )
                ev.citations.append(c.as_citation())
            ev.rag_text = "\n".join(rag_lines)
        ev.tool_calls.append(
            {
                "tool": "search_incident_knowledge",
                "input": {"query": question},
                "ok": bool(chunks),
            }
        )

        # Deduplicate citations (preserve order).
        seen = set()
        deduped = []
        for c in ev.citations:
            key = (c.get("source"), c.get("id"), c.get("label"))
            if key not in seen:
                seen.add(key)
                deduped.append(c)
        ev.citations = deduped
        return ev

    def _synthesizer(self, ev: _Evidence, question: str):
        def _build() -> str:
            if ev.evidence_text:
                text = ev.evidence_text
                if ev.graph_facts and ev.service and ev.service.lower() not in text.lower():
                    text = f"{text}\n\nDependency context:\n{ev.graph_facts}"
                return text
            if ev.graph_facts:
                return ev.graph_facts
            if ev.rag_text:
                return (
                    "I found related past incidents but no direct answer:\n" + ev.rag_text
                )
            return (
                "I couldn't find any matching reliability records for this "
                "organization, so I don't have enough grounded data to answer. "
                "Try connecting integrations or running discovery first."
            )

        return _build

    def _finalize(self, ev: _Evidence, answer_text: str, mode: str) -> dict:
        allowed = build_allowed_set(ev.citations)
        grounded_citations, hallucinated = validate_citations(ev.citations, allowed)
        has_evidence = bool(ev.evidence_text or ev.graph_facts or ev.rag_text)
        tool_results = sum(1 for t in ev.tool_calls if t.get("ok"))
        confidence = score_confidence(
            has_evidence=has_evidence,
            num_citations=len(grounded_citations),
            top_similarity=ev.top_similarity,
            num_tool_results=tool_results,
            mode=mode,
            hallucinated=len(hallucinated),
        )
        grounded = bool(grounded_citations) and has_evidence
        return {
            "answer": answer_text,
            "intent": ev.intent,
            "citations": grounded_citations,
            "sources": ev.sources,
            "tool_calls": ev.tool_calls,
            "confidence": confidence,
            "grounded": grounded,
            "generation_mode": mode,
            "low_confidence": confidence < settings.COPILOT_MIN_CONFIDENCE,
        }

    # -------------------------------------------------------------- chat
    async def chat(self, user, org_context, req) -> dict:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)

        conv = await self._resolve_conversation(organization_id, user, req)
        prior = await self.msg_repo.list_for_conversation(conv.id, organization_id)
        history = memory_mod.to_chat_history(prior)
        mem_summary = memory_mod.to_memory_summary(prior)

        ev = await self._gather(organization_id, req.message, filters=req.filters)
        synthesizer = self._synthesizer(ev, req.message)
        user_prompt = build_user_prompt(
            question=req.message,
            evidence=ev.evidence_text,
            rag_context=ev.rag_text,
            graph_facts=ev.graph_facts,
            memory=mem_summary,
        )

        result = await self.llm.generate(
            system=SYSTEM_PROMPT,
            history=history,
            user_prompt=user_prompt,
            synthesizer=synthesizer,
            organization_id=organization_id,
        )
        final = self._finalize(ev, result.text, result.mode)

        # Persist the turn.
        await self.msg_repo.create(
            conversation_id=conv.id,
            organization_id=organization_id,
            role=GroundedCopilotRole.USER.value,
            content=req.message,
            intent=ev.intent,
        )
        assistant = await self.msg_repo.create(
            conversation_id=conv.id,
            organization_id=organization_id,
            role=GroundedCopilotRole.ASSISTANT.value,
            content=final["answer"],
            intent=final["intent"],
            citations=final["citations"],
            sources=final["sources"],
            tool_calls=final["tool_calls"],
            confidence=final["confidence"],
            grounded=final["grounded"],
            generation_mode=final["generation_mode"],
            model=self.llm.model if not self.llm.offline else "offline",
        )
        conv.updated_at = utcnow()
        await self.audit_repo.log(
            action="copilot_query",
            resource_type="copilot_conversation",
            resource_id=conv.id,
            user_id=user.id,
            organization_id=organization_id,
            details={
                "intent": final["intent"],
                "mode": final["generation_mode"],
                "confidence": final["confidence"],
                "citations": len(final["citations"]),
            },
        )
        # Sprint 61C: meter copilot usage (best-effort; never breaks the turn).
        from app.models.billing import UsageMetric
        from app.services.billing.guards import meter_usage

        await meter_usage(self.session, organization_id, UsageMetric.COPILOT_REQUESTS, enforce=False)
        await self.session.commit()

        final.update(
            {
                "conversation_id": conv.id,
                "message_id": assistant.id,
                "model": self.llm.model if not self.llm.offline else "offline",
                "retrieval_provider": self.retriever.provider,
                "suggested_questions": SUGGESTED_QUESTIONS,
            }
        )
        return final

    # ------------------------------------------------------------ stream
    async def stream_chat(self, user, org_context, req) -> AsyncIterator[dict]:
        """Yield SSE event dicts: {'type': 'token'|'done'|'error', ...}."""
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)

        conv = await self._resolve_conversation(organization_id, user, req)
        prior = await self.msg_repo.list_for_conversation(conv.id, organization_id)
        history = memory_mod.to_chat_history(prior)
        mem_summary = memory_mod.to_memory_summary(prior)

        ev = await self._gather(organization_id, req.message, filters=req.filters)
        synthesizer = self._synthesizer(ev, req.message)
        user_prompt = build_user_prompt(
            question=req.message,
            evidence=ev.evidence_text,
            rag_context=ev.rag_text,
            graph_facts=ev.graph_facts,
            memory=mem_summary,
        )

        # Persist the user turn up front.
        await self.msg_repo.create(
            conversation_id=conv.id,
            organization_id=organization_id,
            role=GroundedCopilotRole.USER.value,
            content=req.message,
            intent=ev.intent,
        )

        yield {"type": "start", "conversation_id": conv.id, "intent": ev.intent}

        chunks: list[str] = []
        mode = "offline" if self.llm.offline else "live"
        async for piece in self.llm.stream(
            system=SYSTEM_PROMPT,
            history=history,
            user_prompt=user_prompt,
            synthesizer=synthesizer,
            organization_id=organization_id,
        ):
            chunks.append(piece)
            yield {"type": "token", "text": piece}

        answer_text = "".join(chunks).strip() or synthesizer()
        final = self._finalize(ev, answer_text, mode)

        assistant = await self.msg_repo.create(
            conversation_id=conv.id,
            organization_id=organization_id,
            role=GroundedCopilotRole.ASSISTANT.value,
            content=answer_text,
            intent=final["intent"],
            citations=final["citations"],
            sources=final["sources"],
            tool_calls=final["tool_calls"],
            confidence=final["confidence"],
            grounded=final["grounded"],
            generation_mode=final["generation_mode"],
            model=self.llm.model if not self.llm.offline else "offline",
        )
        conv.updated_at = utcnow()
        await self.audit_repo.log(
            action="copilot_query",
            resource_type="copilot_conversation",
            resource_id=conv.id,
            user_id=user.id,
            organization_id=organization_id,
            details={"intent": final["intent"], "mode": mode, "streamed": True},
        )
        await self.session.commit()

        yield {
            "type": "done",
            "conversation_id": conv.id,
            "message_id": assistant.id,
            "answer": answer_text,
            "intent": final["intent"],
            "citations": final["citations"],
            "sources": final["sources"],
            "tool_calls": final["tool_calls"],
            "confidence": final["confidence"],
            "grounded": final["grounded"],
            "generation_mode": final["generation_mode"],
            "low_confidence": final["low_confidence"],
        }
