"""Knowledge-graph grounding from the service dependency graph.

Produces factual, citable statements about a service's place in the topology:
its tier, what it depends on, and its blast radius (transitive dependents). These
structured facts ground the LLM's answers about impact and dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.repositories.slo import ServiceRepository
from app.services.graph import GraphService


@dataclass
class GraphGrounding:
    facts: str = ""
    citations: list[dict] = field(default_factory=list)


class KnowledgeGraphGrounder:
    def __init__(self, session):
        self.service_repo = ServiceRepository(session)
        self.graph = GraphService(session)

    async def ground(self, organization_id: str, service_name: str | None) -> GraphGrounding:
        services = await self.service_repo.list_for_org(organization_id)
        if not services:
            return GraphGrounding()
        graph = await self.graph.service_adjacency(organization_id)
        by_id = {s.id: s for s in services}
        by_name = {s.name.lower(): s for s in services if s.name}

        target = by_name.get((service_name or "").lower()) if service_name else None
        if target is None:
            # No specific service in the question — ground the highest blast-radius
            # service so impact questions still have a factual anchor.
            ranked = sorted(
                services,
                key=lambda s: len(graph.dependents(s.id)[1]),
                reverse=True,
            )
            target = ranked[0] if ranked else None
        if target is None:
            return GraphGrounding()

        direct_deps, transitive_deps = graph.dependencies(target.id)
        direct_dependents, transitive_dependents = graph.dependents(target.id)

        dep_names = [by_id[i].name for i in direct_deps if i in by_id]
        dependent_names = [by_id[i].name for i in transitive_dependents if i in by_id]

        lines = [
            f"- Service '{target.name}' (tier {getattr(target, 'tier', 'unknown')}).",
            f"- Depends on {len(direct_deps)} service(s): "
            f"{', '.join(dep_names[:8]) or 'none catalogued'}.",
            f"- Blast radius: a failure impacts {len(transitive_dependents)} "
            f"downstream service(s): {', '.join(dependent_names[:8]) or 'none'}"
            + ("..." if len(dependent_names) > 8 else "")
            + ".",
        ]
        citations = [
            {
                "source": "service",
                "id": target.id,
                "label": target.name,
                "detail": f"{len(transitive_dependents)} dependents",
            }
        ]
        return GraphGrounding(facts="\n".join(lines), citations=citations)
