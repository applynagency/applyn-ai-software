"""Read-only tool registry for the grounded copilot.

Tools are the model's only way to obtain facts. Each tool wraps an existing,
tested, read-only retrieval path and returns ``{"text", "citations"}`` where the
citations reference real org-scoped records. In live mode these are exposed to
the LLM as callable tools; in the deterministic/offline path the engine invokes
them directly. Either way, citations are grounded by construction.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.grounded_copilot.evidence import EvidenceProvider
from app.services.grounded_copilot.knowledge_graph import KnowledgeGraphGrounder
from app.services.grounded_copilot.retrieval import KnowledgeRetriever


@dataclass
class ToolResult:
    text: str
    citations: list[dict]


TOOL_SPECS = [
    {
        "name": "search_reliability_data",
        "description": (
            "Search the organization's reliability data (incidents, deployments, "
            "SLOs, on-call, cost, capacity) and return an authoritative, grounded "
            "answer with citations. Use for any reliability question."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The user's question."}
            },
            "required": ["question"],
        },
    },
    {
        "name": "get_service_blast_radius",
        "description": (
            "Return dependency-graph facts for a service: its tier, direct "
            "dependencies, and transitive downstream dependents (blast radius)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "Service name."}
            },
            "required": ["service"],
        },
    },
    {
        "name": "search_incident_knowledge",
        "description": (
            "Semantic (RAG) search over the org's past incident investigations. "
            "Returns the most similar incidents to the query."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query."}
            },
            "required": ["query"],
        },
    },
]


class CopilotToolExecutor:
    def __init__(self, session, organization_id: str):
        self.session = session
        self.organization_id = organization_id
        self._evidence = EvidenceProvider(session)
        self._retriever = KnowledgeRetriever(session)
        self._grapher = KnowledgeGraphGrounder(session)

    @staticmethod
    def specs() -> list[dict]:
        return TOOL_SPECS

    async def search_reliability_data(self, question: str) -> ToolResult:
        evidence = await self._evidence.gather_evidence(self.organization_id, question)
        citations = [c.model_dump() for c in evidence.get("citations", [])]
        return ToolResult(text=evidence.get("answer", ""), citations=citations)

    async def get_service_blast_radius(self, service: str | None) -> ToolResult:
        grounding = await self._grapher.ground(self.organization_id, service)
        return ToolResult(text=grounding.facts, citations=grounding.citations)

    async def search_incident_knowledge(self, query: str) -> ToolResult:
        chunks = await self._retriever.retrieve(self.organization_id, query)
        if not chunks:
            return ToolResult(text="", citations=[])
        lines = []
        citations = []
        for c in chunks:
            snippet = c.text.strip().replace("\n", " ")
            if len(snippet) > 280:
                snippet = snippet[:280] + "…"
            lines.append(f"[incident:{c.id}] ({c.score:.2f}) {c.label}: {snippet}")
            citations.append(c.as_citation())
        return ToolResult(text="\n".join(lines), citations=citations)

    async def execute(self, name: str, payload: dict) -> ToolResult:
        if name == "search_reliability_data":
            return await self.search_reliability_data(payload.get("question", ""))
        if name == "get_service_blast_radius":
            return await self.get_service_blast_radius(payload.get("service"))
        if name == "search_incident_knowledge":
            return await self.search_incident_knowledge(payload.get("query", ""))
        return ToolResult(text=f"Unknown tool: {name}", citations=[])

    @property
    def top_similarity(self) -> float:
        return getattr(self, "_top_similarity", 0.0)
